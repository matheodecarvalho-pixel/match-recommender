"""Club stature from the UEFA 5-year club coefficient (uefa.com's public ranking feed).

One request. Uses each club's own coefficient points (not the association floor UEFA
adds for clubs with few European games), so a newly promoted side doesn't look big.
Writes data/club_stature.json: {team key: {"points", "rank", "uefa_name"}}.

  python scripts/fetch_stature.py
  python scripts/fetch_stature.py --max-age 7    # skip if refreshed in the last 7 days
"""
import argparse, json, sys
from datetime import date

import requests

import teams
from fd_client import ROOT
from match_teams import norm

URL = "https://comp.uefa.com/v2/coefficients"
HEADERS = {"User-Agent": "personal-match-recommender/0.1 (personal use; github.com/matheodecarvalho-pixel/match-recommender)"}
OUT = ROOT / "data" / "club_stature.json"


def season_year(today):
    """UEFA labels a ranking by the year its season ends (2026-27 -> 2027)."""
    return today.year + 1 if today.month >= 7 else today.year


def key_for(member, registry):
    names = [member.get(k) for k in ("displayOfficialName", "displayName", "internationalName", "displayNameShort")]
    for name in filter(None, names):
        hit = registry.by_name.get(norm(name))
        if hit:
            return hit
    return None


def main(max_age=None):
    if max_age is not None and OUT.exists():
        generated = json.loads(OUT.read_text(encoding="utf-8")).get("generated")
        if generated and (date.today() - date.fromisoformat(generated)).days < max_age:
            print(f"club_stature.json is from {generated}; skipping")
            return 0
    year = season_year(date.today())
    r = requests.get(URL, params={"coefficientRange": "OVERALL", "coefficientType": "MEN_CLUB", "language": "EN",
                                  "page": 1, "pagesize": 500, "seasonYear": year}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    rows = r.json()["data"]["members"]
    registry = teams.load(ROOT)
    clubs, unmatched = {}, []
    for row in rows:
        member, ranking = row["member"], row["overallRanking"]
        key = key_for(member, registry)
        entry = {"points": ranking["totalPoints"], "rank": ranking["position"], "uefa_name": member["displayName"]}
        if key:
            clubs[key] = entry
        else:
            # Clubs outside our 7 leagues (they play in Europe): matched later by name.
            names = {norm(n) for n in (member.get(k) for k in ("displayOfficialName", "displayName",
                     "internationalName", "displayNameShort")) if n}
            unmatched.append({**entry, "names": sorted(names)})
    OUT.write_text(json.dumps({"generated": date.today().isoformat(), "season": year,
                               "source": "https://www.uefa.com/nationalassociations/uefarankings/club/",
                               "clubs": clubs, "others": unmatched},
                              ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{len(clubs)} clubs matched to our teams; {len(unmatched)} other clubs kept by name")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age", type=int)
    sys.exit(main(ap.parse_args().max_age))
