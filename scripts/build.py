"""Score every match in the next `window_days` and write output/matches_ranked.json.

Run after fetch_fd.py and scrape_europe.py:
  python scripts/build.py
"""
import json, sys
from datetime import datetime, timedelta, timezone

import records, revenge, teams
from fd_client import ROOT
from score import context, score_match
from stats import PARIS, load_europe, load_fd, team_results

OUTPUT = ROOT / "output"


def load_rivalries(registry):
    rows = json.loads((ROOT / "data" / "rivalries.json").read_text(encoding="utf-8"))
    return {frozenset((registry.canonical(r["club_a"]), registry.canonical(r["club_b"]))): r for r in rows}


def sort_key(m):
    # Must-watch first, then by score; favourites sit inside that via their boost.
    return (not m["must_watch"], -m["score"], m["kickoff_paris"])


def build(now=None):
    now = now or datetime.now(timezone.utc)
    config = json.loads((ROOT / "config" / "scoring.json").read_text(encoding="utf-8"))
    registry = teams.load(ROOT)
    fd_matches, tables = load_fd(OUTPUT / "raw" / "fd", registry)
    eu_matches, eu_tables, warnings = load_europe(OUTPUT / "europe_matches.json", registry)
    tables.update(eu_tables)
    matches = fd_matches + eu_matches
    results = team_results(matches)
    rivalries = load_rivalries(registry)
    chases = records.track(ROOT, matches, results, tables, registry, warnings)
    snapshot = revenge.load_snapshot(OUTPUT / "transfermarkt")
    if snapshot is None:
        warnings.append("No Transfermarkt snapshot: revenge games not flagged")
    moves = revenge.Revenge(snapshot, registry, config["signals"]["revenge"], warnings)

    # After the 8 league-phase rounds, every Europa/Conference match is a knockout.
    knockout = {comp for comp, table in eu_tables.items() if table and min(r["played"] for r in table) >= 8}

    end = now + timedelta(days=config["window_days"])
    ranked = []
    for m in matches:
        if m["status"] != "upcoming" or not (now - timedelta(hours=2) <= m["kickoff_utc"] < end):
            continue
        extras = {"knockout": m["competition"] in knockout,
                  "record_chases": [c for team in (m["home"], m["away"]) for c in chases.get(team, [])
                                    if c["competition"] == m["competition"]],
                  "revenge": moves.flags(m["home"], m["away"], m["kickoff_utc"])}
        ctx = context(m, results, tables, rivalries, config, extras)
        extras["tier1"] = bool(ctx["rivalry"]) and ctx["rivalry"]["tier"] == 1 and \
            config["must_watch"]["tier_1_rivalry_always"]
        result = score_match(ctx, config)
        kickoff = m["kickoff_utc"].astimezone(PARIS)
        ranked.append({"id": m["id"], "competition": m["competition"],
                       "kickoff_paris": kickoff.isoformat(), "day": kickoff.date().isoformat(),
                       "home": m["home"], "away": m["away"], **result,
                       "tier1_rivalry": bool(extras.get("tier1"))})

    ranked.sort(key=sort_key)
    out = {"generated_at": now.astimezone(PARIS).isoformat(), "window_days": config["window_days"],
           "favourites": config["favourites"]["teams"], "favourite_boost": config["favourites"]["boost"],
           "must_watch_threshold": config["must_watch"]["score_threshold"], "weights": config["weights"],
           "matches": ranked, "warnings": warnings,
           "unmatched_teams": sorted(registry.unmatched)}
    (OUTPUT / "matches_ranked.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    out = build()
    print(f"{len(out['matches'])} matches ranked, {sum(m['must_watch'] for m in out['matches'])} must-watch")
    for m in out["matches"][:15]:
        print(f"{m['score']:3} {'*' if m['must_watch'] else ' '} {m['day']} {m['competition'][:16]:16} "
              f"{m['home']} v {m['away']}  | {m['story']}")
    for w in out["warnings"]:
        print("WARNING:", w, file=sys.stderr)
    if out["unmatched_teams"]:
        print(f"{len(out['unmatched_teams'])} team names not in teams.csv (logged in the output)", file=sys.stderr)
