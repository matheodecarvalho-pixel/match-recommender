"""Final league positions over the last 5 seasons, for the "par" signal.

ESPN standings with ?season=YYYY give the final table of season YYYY-YY+1. 7 leagues x 5
seasons = 35 requests, 4 seconds apart, once a season (finished seasons never change).
Writes data/league_history.json: {league: {season start year: {team key: position}}}.

  python scripts/fetch_league_history.py
"""
import json, sys
from datetime import date

import requests

import teams
from espn_ids import LEAGUES
from fd_client import ROOT
from scrape_europe import BASE, Fetcher

OUT = ROOT / "data" / "league_history.json"
SEASONS = 5


def main():
    today = date.today()
    current = today.year if today.month >= 7 else today.year - 1
    wanted = list(range(current - SEASONS, current))
    history = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"leagues": {}}
    registry = teams.load(ROOT)
    fetcher, failures = Fetcher(), []
    for league, slug in LEAGUES.items():
        if league == "Champions League":
            continue
        seasons = history["leagues"].setdefault(league, {})
        for year in wanted:
            if str(year) in seasons:
                continue  # a finished season never changes
            try:
                data = fetcher.get(f"{BASE}/v2/sports/soccer/{slug}/standings", season=year)
            except requests.RequestException as e:
                failures.append(f"{league} {year}: {e}")
                continue
            table = {}
            for group in data.get("children", []):
                for entry in group["standings"]["entries"]:
                    rank = next((s.get("value") for s in entry["stats"] if s["name"] == "rank"), None)
                    if rank:
                        team = entry["team"]
                        table[registry.from_espn(team["id"], team["displayName"])] = int(rank)
            if table:
                seasons[str(year)] = table
            else:
                failures.append(f"{league} {year}: empty table")
        # Keep only the last SEASONS seasons.
        for old in [y for y in seasons if int(y) not in wanted]:
            del seasons[old]
    history.update({"generated": today.isoformat(), "seasons": wanted,
                    "source": "ESPN standings (site.api.espn.com/apis/v2/sports/soccer/<league>/standings?season=YYYY)"})
    OUT.write_text(json.dumps(history, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{sum(len(s) for s in history['leagues'].values())} league-seasons stored")
    for f in failures:
        print("FAILED:", f, file=sys.stderr)


if __name__ == "__main__":
    main()
