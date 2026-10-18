"""Link football-data.org fixtures to ESPN games, so the site can show live scores.

The browser reads ESPN's public feed directly (it allows cross-origin requests); it just
needs to know which ESPN game each match is. One request per league per month covered by
the scoring window, 4 seconds apart. Europa/Conference League matches already come from
ESPN and need nothing here.

  python scripts/espn_ids.py      # writes output/espn_ids.json
"""
import json, sys
from datetime import date, datetime, timedelta, timezone

import requests

import teams
from fd_client import ROOT
from match_teams import norm
from scrape_europe import BASE, Fetcher, parse
from stats import load_fd

# Our competition name -> ESPN league slug.
LEAGUES = {
    "Premier League": "eng.1", "La Liga": "esp.1", "Serie A": "ita.1", "Bundesliga": "ger.1",
    "Ligue 1": "fra.1", "Eredivisie": "ned.1", "Primeira Liga": "por.1",
    "Champions League": "uefa.champions",
}
OUT = ROOT / "output" / "espn_ids.json"
CACHE = ROOT / "output" / "espn_months"  # finished months, never fetched again


def months(start, end):
    out, d = [], start.replace(day=1)
    while d <= end:
        out.append(d)
        d = (d + timedelta(days=32)).replace(day=1)
    return out


def same_team(registry, our_name, espn_name):
    """ESPN and our key agree, directly or through teams.csv / football-data.org names."""
    return norm(our_name) == norm(espn_name) or registry.by_name.get(norm(espn_name)) == our_name


def link(fixtures, games, registry):
    """{our match id: espn game} for fixtures whose ESPN game kicks off within 3 hours and shares a team."""
    out = {}
    for m in fixtures:
        best = None
        for g in games.get(m["competition"], []):
            kickoff = datetime.fromisoformat(g["kickoff_utc"])
            if abs(kickoff - m["kickoff_utc"]) > timedelta(hours=3):
                continue
            hits = same_team(registry, m["home"], g["home"]) + same_team(registry, m["away"], g["away"])
            if hits and (best is None or hits > best[0]):
                best = (hits, g)
        if best:
            g = best[1]
            out[m["id"]] = {"league": LEAGUES[m["competition"]], "id": g["id"], "us_tv": g.get("us_tv", []),
                            "teams": [g.get("home_espn_id"), g.get("away_espn_id")]}
    return out


def season_start(today):
    return date(today.year if today.month >= 7 else today.year - 1, 7, 1)


def month_games(fetcher, comp, slug, month, today, failures):
    """One league-month of ESPN games; months that have ended come from the cache."""
    path = CACHE / slug / f"{month:%Y%m}.json"
    finished = (month.year, month.month) < (today.year, today.month)
    if finished and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        data = fetcher.get(f"{BASE}/site/v2/sports/soccer/{slug}/scoreboard", dates=f"{month:%Y%m}", limit=500)
    except requests.RequestException as e:
        failures.append(f"{comp} {month:%Y-%m}: {e}")
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    games = parse(data, comp)
    if finished:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(games, ensure_ascii=False), encoding="utf-8")
    return games


def main():
    config = json.loads((ROOT / "config" / "scoring.json").read_text(encoding="utf-8"))
    registry = teams.load(ROOT)
    matches, _ = load_fd(ROOT / "output" / "raw" / "fd", registry)
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=config["window_days"])
    # This week's fixtures (live scores) and every finished match this season (Results tab).
    fixtures = [m for m in matches if (m["status"] == "upcoming" and now - timedelta(hours=3) <= m["kickoff_utc"] < end)
                or m["status"] == "finished"]

    fetcher, games, failures = Fetcher(), {}, []
    for comp, slug in LEAGUES.items():
        for month in months(season_start(now.date()), end.date()):
            games.setdefault(comp, []).extend(month_games(fetcher, comp, slug, month, now.date(), failures))

    ids = link(fixtures, games, registry)
    OUT.write_text(json.dumps(ids, indent=1, sort_keys=True), encoding="utf-8")
    missing = [f"{m['competition']}: {m['home']} v {m['away']}" for m in fixtures if m["id"] not in ids]
    print(f"{len(ids)}/{len(fixtures)} matches linked to ESPN games")
    for line in missing + failures:
        print("  not linked:" if line in missing else "  FAILED:", line, file=sys.stderr)


if __name__ == "__main__":
    main()
