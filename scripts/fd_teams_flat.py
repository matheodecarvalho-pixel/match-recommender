"""Flatten football-data.org team lists into the shape match_teams.py expects.

  python scripts/fd_teams_flat.py   # reads output/raw/fd/*_teams.json, writes output/raw/fd/teams_flat.json
"""
import json

from fd_client import ROOT

RAW = ROOT / "output" / "raw" / "fd"

teams = {}
for path in sorted(RAW.glob("*_teams.json")):
    for t in json.loads(path.read_text(encoding="utf-8"))["teams"]:
        teams[t["id"]] = {"id": t["id"], "name": t["name"], "short_name": t.get("shortName"),
                          "country": (t.get("area") or {}).get("name"), "competition": path.name.split("_")[0]}
(RAW / "teams_flat.json").write_text(json.dumps(list(teams.values()), ensure_ascii=False, indent=1), encoding="utf-8")
print(len(teams), "teams")
