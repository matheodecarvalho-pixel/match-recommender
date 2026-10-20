"""Player season stats per club from ESPN's public team rosters (this season and last), for team pages.

ESPN gives league totals per player: appearances, sub appearances, goals, assists, shots, shots
on target, cards, and saves/goals conceded for keepers. No minutes and no match ratings (those
are paid data elsewhere), so per-game numbers are per appearance.

Cache: output/players/<league>-<espn team id>-<season>.json. Last season is fetched once; this
season again only after the club has played since the last fetch. Requests are 4 seconds apart.

  python scripts/fetch_players.py
"""
import json, sys, time
from datetime import date, datetime, timezone

import requests

import teams
from fd_client import ROOT
from stats import load_fd

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "personal-match-recommender/0.1 (personal use, 1 run/day)"}
DELAY_SECONDS = 4
CACHE = ROOT / "output" / "players"
KEEP = ("appearances", "subIns", "totalGoals", "goalAssists", "totalShots", "shotsOnTarget",
        "yellowCards", "redCards", "saves", "goalsConceded")


def season_years(today=None):
    """ESPN names a season by the year it starts: (this season, last season)."""
    today = today or date.today()
    start = today.year if today.month >= 7 else today.year - 1
    return start, start - 1


def clubs():
    """Our team name -> (ESPN league slug, ESPN team id, date of its latest finished league match)."""
    registry = teams.load(ROOT)
    matches, _ = load_fd(ROOT / "output" / "raw" / "fd", registry)
    by_id = {m["id"]: m for m in matches}
    ids = json.loads((ROOT / "output" / "espn_ids.json").read_text(encoding="utf-8"))
    out = {}
    for mid, link in ids.items():
        m = by_id.get(mid)
        if not m or m["competition"] == "Champions League" or not link.get("teams"):
            continue
        for team, espn_id in zip((m["home"], m["away"]), link["teams"]):
            last = m["kickoff_utc"].date().isoformat() if m["status"] == "finished" else ""
            slug, tid, seen = out.get(team, (link["league"], espn_id, ""))
            out[team] = (slug, tid, max(seen, last))
    return out


def slim(data):
    players = []
    for a in data.get("athletes", []):
        stats = {}
        for cat in (a.get("statistics") or {}).get("splits", {}).get("categories", []):
            for s in cat.get("stats", []):
                if s["name"] in KEEP:
                    stats[s["name"]] = s.get("value") or 0
        if not stats.get("appearances"):
            continue
        players.append({"id": a["id"], "name": a.get("displayName"), "position": (a.get("position") or {}).get("abbreviation"),
                        "stats": stats})
    return players


def main():
    now, last = season_years()
    CACHE.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)
    fetched, failures = 0, []
    for team, (slug, tid, played) in sorted(clubs().items()):
        for season in (now, last):
            path = CACHE / f"{slug}-{tid}-{season}.json"
            if path.exists():
                old = json.loads(path.read_text(encoding="utf-8"))
                if season == last or old["fetched"] >= played:
                    continue
            try:
                time.sleep(DELAY_SECONDS)
                r = session.get(f"{BASE}/{slug}/teams/{tid}/roster", params={"season": season}, timeout=30)
                r.raise_for_status()
            except requests.RequestException as e:
                failures.append(f"{team} {season}: {e}")
                continue
            path.write_text(json.dumps({"team": team, "league": slug, "espn_id": tid, "season": season,
                                        "fetched": datetime.now(timezone.utc).date().isoformat(),
                                        "players": slim(r.json())}, ensure_ascii=False, indent=1), encoding="utf-8")
            fetched += 1
    print(f"{fetched} rosters fetched")
    for f in failures:
        print("FAILED:", f, file=sys.stderr)


if __name__ == "__main__":
    main()
