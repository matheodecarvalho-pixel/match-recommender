"""Season averages per team that hint at a playing style, from ESPN monthly scoreboards.

Per team: possession %, shots for/against, shots on target for/against, goals for/against,
corners and fouls per game, over every finished match this season in our 7 leagues and the
3 European competitions. One request per competition per month, 4 seconds apart.
Writes data/style_stats.json.

  python scripts/fetch_style_stats.py
"""
import json, sys
from datetime import date

import requests

import teams
from espn_ids import months, season_start
from fd_client import ROOT
from scrape_europe import BASE, Fetcher

SLUGS = ["eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "ned.1", "por.1",
         "uefa.champions", "uefa.europa", "uefa.europa.conf"]
FIELDS = {"possessionPct": "possession", "totalShots": "shots", "shotsOnTarget": "on_target",
          "wonCorners": "corners", "foulsCommitted": "fouls", "totalGoals": "goals"}
OUT = ROOT / "data" / "style_stats.json"


def side_stats(competitor):
    stats = {s["name"]: s.get("displayValue") for s in competitor.get("statistics", [])}
    out = {}
    for name, key in FIELDS.items():
        try:
            out[key] = float(stats[name])
        except (KeyError, TypeError, ValueError):
            return None  # incomplete stats: skip the match
    return out


def main():
    registry = teams.load(ROOT)
    fetcher, today, failures = Fetcher(), date.today(), []
    totals, leagues = {}, {}
    for slug in SLUGS:
        for month in months(season_start(today), today):
            try:
                data = fetcher.get(f"{BASE}/site/v2/sports/soccer/{slug}/scoreboard", dates=f"{month:%Y%m}", limit=500)
            except requests.RequestException as e:
                failures.append(f"{slug} {month:%Y-%m}: {e}")
                continue
            for e in data.get("events", []):
                comp = e["competitions"][0]
                if not e["status"]["type"].get("completed") or len(comp["competitors"]) != 2:
                    continue
                a, b = comp["competitors"]
                sa, sb = side_stats(a), side_stats(b)
                if not sa or not sb:
                    continue
                for me, mine, theirs in ((a, sa, sb), (b, sb, sa)):
                    key = registry.from_espn(me["team"]["id"], me["team"]["displayName"])
                    t = totals.setdefault(key, {"games": 0})
                    t["games"] += 1
                    for k, v in mine.items():
                        t[k] = t.get(k, 0) + v
                    for k in ("shots", "on_target", "goals"):
                        t[k + "_against"] = t.get(k + "_against", 0) + theirs[k]
                    if not slug.startswith("uefa"):
                        leagues[key] = slug
    teams_out = {}
    for key, t in totals.items():
        n = t.pop("games")
        teams_out[key] = {"games": n, "league": leagues.get(key), **{k: round(v / n, 2) for k, v in t.items()}}
    OUT.write_text(json.dumps({"generated": today.isoformat(), "source": "ESPN scoreboards (team statistics per match)",
                               "teams": teams_out}, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{len(teams_out)} teams")
    for f in failures:
        print("FAILED:", f, file=sys.stderr)


if __name__ == "__main__":
    main()
