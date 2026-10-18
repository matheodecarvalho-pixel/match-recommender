"""Recent domestic results for European opponents outside our 7 leagues.

Bodø/Glimt, Ferencváros or Sabah only appear in our data through their European games, so
their form and goals were empty. This fetches each such club's schedule from ESPN (one
request per club, 4 seconds apart) for the clubs playing in Europe in the coming days, and
keeps their last finished matches in output/team_forms.json. A club fetched today is not
fetched again today.

  python scripts/fetch_team_forms.py
"""
import json, sys
from datetime import date, datetime, timedelta, timezone

import requests

from fd_client import ROOT
from scrape_europe import BASE, Fetcher

OUT = ROOT / "output" / "team_forms.json"
KEEP = 10  # finished matches kept per club


def domestic_espn_ids():
    """ESPN ids of clubs in our 7 leagues: they already have full form from football-data.org."""
    ids = set()
    for path in (ROOT / "output" / "espn_months").glob("*/*.json"):
        if path.parent.name == "uefa.champions":
            continue
        for g in json.loads(path.read_text(encoding="utf-8")):
            ids.update({g.get("home_espn_id"), g.get("away_espn_id")})
    return ids - {None}


def targets(window_days):
    """{espn id: name} for clubs in European fixtures over the coming days."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=window_days + 1)
    out = {}
    europe = ROOT / "output" / "europe_matches.json"
    if europe.exists():
        for m in json.loads(europe.read_text(encoding="utf-8"))["matches"]:
            if m["status"] != "finished" and now - timedelta(hours=3) <= datetime.fromisoformat(m["kickoff_utc"]) < end:
                out[m["home_espn_id"]] = m["home"]
                out[m["away_espn_id"]] = m["away"]
    ids = ROOT / "output" / "espn_ids.json"
    if ids.exists():
        for link in json.loads(ids.read_text(encoding="utf-8")).values():
            if link["league"] == "uefa.champions":
                for tid in link.get("teams") or []:
                    if tid:
                        out.setdefault(tid, None)
    return out


def finished_matches(data, team_id):
    rows = []
    for e in data.get("events", []):
        comp = e["competitions"][0]
        if not comp.get("status", {}).get("type", {}).get("completed"):
            continue
        sides = {c["team"]["id"]: c for c in comp["competitors"]}
        if team_id not in sides or len(sides) != 2:
            continue
        me = sides.pop(team_id)
        other = next(iter(sides.values()))
        score = lambda c: int((c.get("score") or {}).get("value", 0))
        rows.append({"date": e["date"], "league": (e.get("league") or {}).get("name") or data.get("season", {}).get("displayName"),
                     "opponent": other["team"]["displayName"], "gf": score(me), "ga": score(other)})
    return sorted(rows, key=lambda r: r["date"])[-KEEP:]


def main():
    config = json.loads((ROOT / "config" / "scoring.json").read_text(encoding="utf-8"))
    forms = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    skip = domestic_espn_ids()
    today = date.today().isoformat()
    fetcher, failures, fetched = Fetcher(), [], 0
    for tid, name in targets(config["window_days"]).items():
        if tid in skip or forms.get(tid, {}).get("fetched") == today:
            continue
        try:
            data = fetcher.get(f"{BASE}/site/v2/sports/soccer/all/teams/{tid}/schedule")
        except requests.RequestException as e:
            failures.append(f"{name or tid}: {e}")
            continue
        team = data.get("team") or {}
        forms[tid] = {"name": team.get("displayName") or name, "fetched": today, "matches": finished_matches(data, tid)}
        fetched += 1
    OUT.write_text(json.dumps(forms, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{fetched} clubs fetched, {len(forms)} kept")
    for f in failures:
        print("FAILED:", f, file=sys.stderr)


if __name__ == "__main__":
    main()
