"""Fetch season matches, standings and top scorers for the 8 football-data.org competitions.

Writes raw JSON to output/raw/fd/. 24 calls, about 3 minutes with the throttle.

Also keeps two small files in git for club revenge and European classics:
  output/history/fd_CL_<season>.json   last season's Champions League (fetched once)
  output/h2h_cache.json                European meetings per pair, for upcoming CL fixtures

  python scripts/fetch_fd.py            # matches, standings, scorers
  python scripts/fetch_fd.py --teams    # also team lists (only needed for match_teams.py)
"""
import argparse, json, sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from fd_client import COMPETITIONS, ROOT, Client

RAW = ROOT / "output" / "raw" / "fd"
HISTORY = ROOT / "output" / "history"
H2H = ROOT / "output" / "h2h_cache.json"


def slim(m):
    """The fields club revenge needs from a football-data.org match."""
    team = lambda t: {"id": t["id"], "name": t["name"], "shortName": t.get("shortName")}
    return {"id": m["id"], "utcDate": m["utcDate"], "status": m["status"], "stage": m.get("stage"),
            "homeTeam": team(m["homeTeam"]), "awayTeam": team(m["awayTeam"]),
            "score": {"winner": m["score"].get("winner"), "fullTime": m["score"]["fullTime"]}}


def previous_cl_season(client, failures):
    """Last season's Champions League, fetched once and kept in git."""
    current = json.loads((RAW / "CL_matches.json").read_text(encoding="utf-8"))["filters"]["season"]
    season = int(current) - 1
    path = HISTORY / f"fd_CL_{season}.json"
    if path.exists():
        return
    try:
        data = client.get("/competitions/CL/matches", season=season)
    except requests.RequestException as e:
        failures.append(f"Champions League {season}: {e}")
        return
    HISTORY.mkdir(parents=True, exist_ok=True)
    matches = [slim(m) for m in data["matches"] if m["homeTeam"].get("id") and m["awayTeam"].get("id")]
    path.write_text(json.dumps({"season": season, "matches": matches}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"Champions League {season}: {len(matches)} matches saved")


def pair_key(a, b):
    return "-".join(str(i) for i in sorted((a, b)))


def head_to_heads(client, failures):
    """European meetings for each Champions League fixture in the coming days.

    A pair is fetched again only when it has played each other since the last fetch.
    """
    config = json.loads((ROOT / "config" / "scoring.json").read_text(encoding="utf-8"))
    since = config["signals"]["rivalry"]["european_classic"]["since"]
    horizon = datetime.now(timezone.utc) + timedelta(days=config["window_days"] + 1)
    cache = json.loads(H2H.read_text(encoding="utf-8")) if H2H.exists() else {}
    matches = json.loads((RAW / "CL_matches.json").read_text(encoding="utf-8"))["matches"]
    played = {}
    for m in matches:
        if m["status"] == "FINISHED":
            key = pair_key(m["homeTeam"]["id"], m["awayTeam"]["id"])
            played[key] = max(played.get(key, ""), m["utcDate"][:10])
    for m in matches:
        if m["status"] not in ("SCHEDULED", "TIMED") or not m["homeTeam"].get("id") or not m["awayTeam"].get("id"):
            continue
        if datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")) > horizon:
            continue
        key = pair_key(m["homeTeam"]["id"], m["awayTeam"]["id"])
        if key in cache and played.get(key, "") <= cache[key]["fetched"]:
            continue
        try:
            data = client.get(f"/matches/{m['id']}/head2head", limit=50)
        except requests.RequestException as e:
            failures.append(f"head2head {m['homeTeam']['name']} v {m['awayTeam']['name']}: {e}")
            continue
        meetings = sorted({(x["utcDate"][:10], x["competition"]["name"]) for x in data["matches"]
                           if x["status"] == "FINISHED" and x["competition"]["name"].startswith("UEFA")
                           and x["utcDate"][:10] >= since})
        cache[key] = {"fetched": datetime.now(timezone.utc).date().isoformat(),
                      "teams": [m["homeTeam"]["name"], m["awayTeam"]["name"]],
                      "meetings": [{"date": d, "competition": c} for d, c in meetings]}
    H2H.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


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
    if (RAW / "CL_matches.json").exists():
        previous_cl_season(client, failures)
        head_to_heads(client, failures)
    save("_fetched_at.json", {"fetched_at": datetime.now(ZoneInfo("Europe/Paris")).isoformat(),
                              "failures": failures})
    for f in failures:
        print("FAILED:", f, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", action="store_true")
    sys.exit(main(ap.parse_args().teams))
