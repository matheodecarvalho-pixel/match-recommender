"""One calendar feed per team (.ics) with its whole season, for calendar apps to subscribe to.

Calendar apps re-read a subscribed feed on their own (Apple: as often as every hour if set,
Google: a few times a day), so a moved kickoff, a postponement or a newly set time reaches
them without anyone re-importing. Each match keeps the same UID, so it is updated, never duplicated.

  python scripts/calendars.py _site/calendars     # after build.py
"""
import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import teams
from fd_client import ROOT
from match_teams import norm
from stats import CRESTS, PARIS, load_europe, load_fd

SITE = "https://matheodecarvalho-pixel.github.io/match-recommender/"
MATCH_LENGTH = timedelta(hours=2)
REMINDER = "-PT1H"  # an hour before kickoff


def slug(team):
    return norm(team).replace(" ", "-")


def escape(text):
    return text.replace("\\", "\\\\").replace(";", "\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    """RFC 5545: lines longer than 75 bytes continue on the next line after a space."""
    raw, out = line.encode("utf-8"), []
    while len(raw) > 75:
        cut = 75 if not out else 74
        while (raw[cut] & 0xC0) == 0x80:  # don't split a UTF-8 character
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n ".join(out)


def utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def event(m, ranked, stamp):
    home, away = m["home"], m["away"]
    if m["status"] == "finished" and m["home_goals"] is not None:
        title = f"{home} {m['home_goals']}–{m['away_goals']} {away}"
    else:
        title = f"{home} v {away}"
    if m.get("postponed"):
        title = "Postponed: " + title
    notes = [m["competition"]]
    r = ranked.get(m["id"])
    if r and m["status"] == "upcoming":
        notes.append(f"eyeball: {r['score']}/100" + (" · Must-watch" if r["must_watch"] else ""))
    lines = ["BEGIN:VEVENT", f"UID:eyeball-{m['id']}@matheodecarvalho-pixel.github.io", f"DTSTAMP:{stamp}",
             f"SUMMARY:{escape(title)}"]
    if m.get("time_confirmed", True):
        lines += [f"DTSTART:{utc(m['kickoff_utc'])}", f"DTEND:{utc(m['kickoff_utc'] + MATCH_LENGTH)}"]
    else:
        # Date known, kickoff time not set yet: an all-day event until the league sets it.
        day = m["kickoff_utc"].astimezone(PARIS).date()
        lines += [f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
                  "TRANSP:TRANSPARENT"]
        notes.append("Kickoff time not set yet: this event updates once the league sets it")
    notes.append(SITE)
    lines.append(f"DESCRIPTION:{escape(chr(10).join(notes))}")
    if m.get("postponed"):
        lines.append("STATUS:CANCELLED")
    elif m["status"] == "upcoming" and m.get("time_confirmed", True):
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{escape(home + ' v ' + away)} in 1 hour",
                  f"TRIGGER:{REMINDER}", "END:VALARM"]
    lines.append("END:VEVENT")
    return lines


def calendar(team, matches, ranked, stamp):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//eyeball//team calendar//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", f"X-WR-CALNAME:{escape(team)} · eyeball",
             f"X-WR-CALDESC:{escape(team)}: every match this season, kept up to date by eyeball",
             "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H"]
    for m in matches:
        lines += event(m, ranked, stamp)
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    registry = teams.load(ROOT)
    fd, _ = load_fd(ROOT / "output" / "raw" / "fd", registry)
    eu, _, _ = load_europe(ROOT / "output" / "europe_matches.json", registry)
    ranked_path = ROOT / "output" / "matches_ranked.json"
    ranked = {m["id"]: m for m in json.loads(ranked_path.read_text(encoding="utf-8"))["matches"]} \
        if ranked_path.exists() else {}
    by_team = {}
    for m in sorted(fd + eu, key=lambda m: m["kickoff_utc"]):
        if m["status"] == "other" and not m.get("postponed"):
            continue
        for t in (m["home"], m["away"]):
            by_team.setdefault(t, []).append(m)
    stamp = utc(datetime.now(timezone.utc))
    index = []
    for team, matches in by_team.items():
        name = slug(team)
        (out / f"{name}.ics").write_bytes(calendar(team, matches, ranked, stamp).encode("utf-8"))
        upcoming = [m for m in matches if m["status"] == "upcoming"]
        index.append({"team": team, "file": f"{name}.ics", "crest": CRESTS.get(team),
                      "competitions": sorted({m["competition"] for m in matches}), "upcoming": len(upcoming)})
    index.sort(key=lambda r: r["team"])
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(index)} team calendars written to {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "output" / "calendars")
