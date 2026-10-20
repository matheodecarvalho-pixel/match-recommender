"""Daily fetch for Europa League and Conference League: fixtures, results, league-phase table.

Source: ESPN's public JSON feed (no key, unofficial and undocumented), one request per
competition per date, e.g.
  https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard?dates=20261022
Kickoff times come in UTC and are converted to Europe/Paris with zoneinfo.

Football Web Pages, the original source, sits behind a Cloudflare bot check (403), so it
was dropped rather than worked around.

Each date is cached in output/europe_cache/; a past date whose matches are all final is
never fetched again. Requests are 4 seconds apart.

  python scripts/scrape_europe.py                    # 3 days back, 10 ahead
  python scripts/scrape_europe.py --since 20260901   # one-off backfill (cached dates are skipped)
  python scripts/scrape_europe.py --debug 20261022 uefa.europa
"""
import argparse, json, sys, time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from fd_client import ROOT

BASE = "https://site.api.espn.com/apis"
COMPETITIONS = {
    "uefa.europa": "Europa League",
    "uefa.europa.conf": "Conference League",
}
PARIS = ZoneInfo("Europe/Paris")
HEADERS = {"User-Agent": "personal-match-recommender/0.1 (personal use, 1 run/day)"}
DELAY_SECONDS = 4
CACHE = ROOT / "output" / "europe_cache"
HISTORY = ROOT / "output" / "europe_history"
HISTORY_MONTHS = 13  # club revenge looks back 12 months; one extra for safety
AHEAD_MONTHS = 9  # fixtures for team calendars: this month to the end of the season
OUT = ROOT / "output" / "europe_matches.json"
H2H = ROOT / "output" / "h2h_espn.json"
H2H_DAYS = 8  # head-to-heads for the coming week's games (team pages)

STATUS = {"STATUS_SCHEDULED": "scheduled", "STATUS_FULL_TIME": "finished",
          "STATUS_FINAL_AET": "finished", "STATUS_FINAL_PEN": "finished",
          "STATUS_POSTPONED": "postponed", "STATUS_CANCELED": "cancelled"}


class Fetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._last = 0.0

    def get(self, url, **params):
        wait = DELAY_SECONDS - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        r = self.session.get(url, params=params or None, timeout=30)
        r.raise_for_status()
        return r.json()


def parse(data, competition):
    matches = []
    for e in data.get("events", []):
        comp = e["competitions"][0]
        sides = {c["homeAway"]: c for c in comp["competitors"]}
        if set(sides) != {"home", "away"}:
            continue
        kickoff = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(timezone.utc)
        kind = e["status"]["type"]
        status = STATUS.get(kind["name"], "finished" if kind.get("completed") else "live")
        row = {"id": e["id"], "competition": competition,
               "kickoff_utc": kickoff.isoformat(), "kickoff_paris": kickoff.astimezone(PARIS).isoformat(),
               "home": sides["home"]["team"]["displayName"], "home_espn_id": sides["home"]["team"]["id"],
               "away": sides["away"]["team"]["displayName"], "away_espn_id": sides["away"]["team"]["id"],
               "status": status, "stage": (e.get("season") or {}).get("slug"),
               "season": (e.get("season") or {}).get("year"),
               # ESPN only lists US channels, per match.
               "us_tv": list(dict.fromkeys(n for b in comp.get("broadcasts", []) for n in b.get("names", [])))}
        if status == "finished":
            row["home_goals"] = int(sides["home"]["score"])
            row["away_goals"] = int(sides["away"]["score"])
            # ESPN flags the winner, which also settles penalty shootouts.
            row["winner"] = next((side for side in ("home", "away") if sides[side].get("winner")), None)
        matches.append(row)
    return matches


def is_settled(day, matches, today):
    """A past date is final once every match on it is finished (or there were none)."""
    if day >= today - timedelta(days=1):
        return False
    return all(m["status"] in ("finished", "postponed", "cancelled") for m in matches)


def day_matches(fetcher, slug, name, day, today, warnings):
    path = CACHE / slug / f"{day:%Y%m%d}.json"
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached.get("settled"):
            return cached["matches"]
    try:
        data = fetcher.get(f"{BASE}/site/v2/sports/soccer/{slug}/scoreboard", dates=f"{day:%Y%m%d}")
    except requests.RequestException as e:
        warnings.append(f"{name} {day}: request failed ({e})")
        return json.loads(path.read_text(encoding="utf-8"))["matches"] if path.exists() else []
    matches = parse(data, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"settled": is_settled(day, matches, today), "matches": matches},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    return matches


def month_matches(fetcher, slug, name, month, today, warnings):
    """One past month of results, for club revenge. A month that has ended is fetched once."""
    path = HISTORY / slug / f"{month:%Y%m}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["matches"]
    try:
        data = fetcher.get(f"{BASE}/site/v2/sports/soccer/{slug}/scoreboard", dates=f"{month:%Y%m}", limit=300)
    except requests.RequestException as e:
        warnings.append(f"{name} {month:%Y-%m} history: request failed ({e})")
        return []
    matches = [m for m in parse(data, name) if m["status"] == "finished"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"matches": matches}, ensure_ascii=False, indent=1), encoding="utf-8")
    return matches


def fixtures_ahead(fetcher, slug, name, today, warnings):
    """The rest of the season's fixtures, one request per month (for team calendars). Never cached:
    kickoff times and dates move."""
    out, y, m = [], today.year, today.month
    for _ in range(AHEAD_MONTHS):
        try:
            data = fetcher.get(f"{BASE}/site/v2/sports/soccer/{slug}/scoreboard", dates=f"{y}{m:02d}", limit=300)
            out.extend(r for r in parse(data, name) if r["status"] != "finished")
        except requests.RequestException as e:
            warnings.append(f"{name} {y}-{m:02d} fixtures: request failed ({e})")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        if (y, m) > (today.year + (today.month > 6), 6):
            break  # the season ends in May
    return out


def head_to_heads(fetcher, matches, today, warnings):
    """Last meetings (ESPN's "season series", up to 5) for each Europa/Conference League game in the
    coming days, kept per game; fetched once."""
    cache = json.loads(H2H.read_text(encoding="utf-8")) if H2H.exists() else {}
    horizon = (datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=H2H_DAYS)).isoformat()
    slugs = {name: slug for slug, name in COMPETITIONS.items()}
    for m in matches:
        if m["status"] != "scheduled" or m["id"] in cache or m["kickoff_utc"] > horizon:
            continue
        try:
            data = fetcher.get(f"{BASE}/site/v2/sports/soccer/{slugs[m['competition']]}/summary", event=m["id"])
        except requests.RequestException as e:
            warnings.append(f"head-to-head {m['home']} v {m['away']}: request failed ({e})")
            continue
        meetings = []
        for series in data.get("seasonseries") or []:
            if series.get("type") != "head-to-head":
                continue
            for e in series.get("events", []):
                if not (e.get("statusType") or {}).get("completed"):
                    continue
                side = {c["homeAway"]: c for c in e["competitors"]}
                meetings.append({"date": e["date"][:10], "competition": e.get("competitionName") or "",
                                 "home_espn_id": side["home"]["team"]["id"], "away_espn_id": side["away"]["team"]["id"],
                                 "home_goals": int(side["home"].get("score") or 0), "away_goals": int(side["away"].get("score") or 0)})
        cache[m["id"]] = {"fetched": today.isoformat(), "home_espn_id": m["home_espn_id"],
                          "away_espn_id": m["away_espn_id"], "meetings": meetings}
    H2H.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def past_months(today, count):
    """First day of each of the `count` months before the current one, oldest first."""
    months, y, m = [], today.year, today.month
    for _ in range(count):
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        months.append(date(y, m, 1))
    return months[::-1]


def standings(fetcher, slug, name, warnings):
    try:
        data = fetcher.get(f"{BASE}/v2/sports/soccer/{slug}/standings")
    except requests.RequestException as e:
        warnings.append(f"{name} standings: request failed ({e})")
        return []
    table = []
    for group in data.get("children", []):
        for entry in group["standings"]["entries"]:
            stats = {s["name"]: s.get("value") for s in entry["stats"]}
            table.append({"team": entry["team"]["displayName"], "espn_id": entry["team"]["id"],
                          "position": int(stats.get("rank") or 0), "played": int(stats.get("gamesPlayed") or 0),
                          "points": int(stats.get("points") or 0), "goals_for": int(stats.get("pointsFor") or 0),
                          "goals_against": int(stats.get("pointsAgainst") or 0)})
    if not table:
        warnings.append(f"{name}: empty league-phase table")
    return sorted(table, key=lambda r: r["position"])


def run(back=3, ahead=10, since=None):
    fetcher = Fetcher()
    today = date.today()
    start = since or today - timedelta(days=back)
    found, history, later, tables, warnings = [], [], [], {}, []
    for slug, name in COMPETITIONS.items():
        for month in past_months(today, HISTORY_MONTHS):
            history.extend(month_matches(fetcher, slug, name, month, today, warnings))
        # Dates cached by earlier runs are included, so form covers the whole season.
        folder = CACHE / slug
        days = {start + timedelta(days=i) for i in range((today + timedelta(days=ahead) - start).days + 1)}
        if folder.exists():
            days |= {datetime.strptime(p.stem, "%Y%m%d").date() for p in folder.glob("*.json")}
        window = 0
        for day in sorted(days):
            rows = day_matches(fetcher, slug, name, day, today, warnings)
            if today - timedelta(days=back) <= day <= today + timedelta(days=ahead):
                window += len(rows)
            found.extend(rows)
        # Two weeks without a match in season is suspicious (feed change or blocked request).
        if not window and (today.month >= 9 or today.month <= 5):
            warnings.append(f"{name}: 0 matches between {back} days ago and {ahead} days ahead")
        tables[name] = standings(fetcher, slug, name, warnings)
        later.extend(fixtures_ahead(fetcher, slug, name, today, warnings))

    unique = {m["id"]: m for m in found}
    data = {"fetched_at": datetime.now(PARIS).isoformat(), "source": "ESPN public JSON feed",
            "matches": sorted(unique.values(), key=lambda m: (m["kickoff_utc"], m["competition"], m["home"])),
            "standings": tables, "warnings": warnings,
            # Every fixture still to play this season, for the team calendars.
            "fixtures_ahead": sorted({m["id"]: m for m in later}.values(), key=lambda m: m["kickoff_utc"]),
            # Finished matches from the months before this one (club revenge looks back a year).
            "history": sorted({m["id"]: m for m in history}.values(), key=lambda m: m["kickoff_utc"])}
    head_to_heads(fetcher, data["matches"], today, warnings)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(data['matches'])} matches saved to {OUT.relative_to(ROOT)}")
    for w in warnings:
        print("WARNING:", w, file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", nargs=2, metavar=("YYYYMMDD", "SLUG"), help="fetch one date, print parsed rows")
    ap.add_argument("--back", type=int, default=3)
    ap.add_argument("--ahead", type=int, default=10)
    ap.add_argument("--since", type=lambda s: datetime.strptime(s, "%Y%m%d").date())
    a = ap.parse_args()
    if a.debug:
        data = Fetcher().get(f"{BASE}/site/v2/sports/soccer/{a.debug[1]}/scoreboard", dates=a.debug[0])
        print(json.dumps(parse(data, COMPETITIONS.get(a.debug[1], a.debug[1])), ensure_ascii=False, indent=1))
    else:
        run(a.back, a.ahead, a.since)
