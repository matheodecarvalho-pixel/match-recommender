"""Fetch season matches, standings and top scorers for the 8 football-data.org competitions.

Writes raw JSON to output/raw/fd/. 24 calls, about 3 minutes with the throttle.

  python scripts/fetch_fd.py            # matches, standings, scorers
  python scripts/fetch_fd.py --teams    # also team lists (only needed for match_teams.py)
"""
import argparse, json, sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from fd_client import COMPETITIONS, ROOT, Client

RAW = ROOT / "output" / "raw" / "fd"


def save(name, data):
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def main(with_teams=False):
    client = Client()
    endpoints = {"matches": {}, "standings": {}, "scorers": {"limit": 100}}
    if with_teams:
        endpoints["teams"] = {}
    failures = []
    for code, name in COMPETITIONS.items():
        for endpoint, params in endpoints.items():
            try:
                data = client.get(f"/competitions/{code}/{endpoint}", **params)
            except requests.RequestException as e:
                failures.append(f"{name} {endpoint}: {e}")
                continue
            save(f"{code}_{endpoint}.json", data)
            count = len(data.get(endpoint, [])) if endpoint != "standings" else len(data.get("standings", []))
            print(f"{name:18} {endpoint:9} {count}")
    save("_fetched_at.json", {"fetched_at": datetime.now(ZoneInfo("Europe/Paris")).isoformat(),
                              "failures": failures})
    for f in failures:
        print("FAILED:", f, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", action="store_true")
    sys.exit(main(ap.parse_args().teams))
