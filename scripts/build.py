"""Score every match in the next `window_days` and write output/matches_ranked.json.

Run after fetch_fd.py and scrape_europe.py:
  python scripts/build.py
"""
import json, sys
from datetime import datetime, timedelta, timezone

import euro_results, records, revenge, teams
from fd_client import ROOT
from match_teams import norm
from score import context, score_match
from stats import PARIS, load_europe, load_fd, team_results

OUTPUT = ROOT / "output"


def load_rivalries(registry):
    rows = json.loads((ROOT / "data" / "rivalries.json").read_text(encoding="utf-8"))
    return {frozenset((registry.canonical(r["club_a"]), registry.canonical(r["club_b"]))): r for r in rows}


ESPN_SLUGS = {"Europa League": "uefa.europa", "Conference League": "uefa.europa.conf"}


def espn_link(m, ids, us_tv):
    """Which ESPN game this is (for live scores) and its US channels. None when unknown."""
    if m["id"].startswith("espn-"):
        eid = m["id"][len("espn-"):]
        return {"league": ESPN_SLUGS[m["competition"]], "id": eid, "us_tv": us_tv.get(eid, [])}
    return ids.get(m["id"])


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

    european = euro_results.load(ROOT, registry)
    elims = euro_results.eliminations(european)
    meetings = euro_results.european_meetings(ROOT)
    stature_path = ROOT / "data" / "club_stature.json"
    clubs = json.loads(stature_path.read_text(encoding="utf-8"))["clubs"] if stature_path.exists() else {}
    if not clubs:
        warnings.append("No club_stature.json: big-match signal scores 0")
    add_other_clubs(clubs, stature_path, matches)
    history_path = ROOT / "data" / "league_history.json"
    history = json.loads(history_path.read_text(encoding="utf-8"))["leagues"] if history_path.exists() else {}
    add_team_forms(results, registry)
    ids_path = OUTPUT / "espn_ids.json"
    espn_ids = json.loads(ids_path.read_text(encoding="utf-8")) if ids_path.exists() else {}
    europe_path = OUTPUT / "europe_matches.json"
    us_tv = {m["id"]: m.get("us_tv", []) for m in json.loads(europe_path.read_text(encoding="utf-8"))["matches"]} \
        if europe_path.exists() else {}

    # After the 8 league-phase rounds, every Europa/Conference match is a knockout.
    knockout = {comp for comp, table in eu_tables.items() if table and min(r["played"] for r in table) >= 8}

    end = now + timedelta(days=config["window_days"])
    ranked = []
    for m in matches:
        if m["status"] != "upcoming" or not (now - timedelta(hours=2) <= m["kickoff_utc"] < end):
            continue
        extras = {"knockout": m["competition"] in knockout, "stature": clubs, "history": history,
                  "record_chases": [c for team in (m["home"], m["away"]) for c in chases.get(team, [])
                                    if c["competition"] == m["competition"]],
                  "revenge": moves.flags(m["home"], m["away"], m["kickoff_utc"]),
                  "club_revenge": euro_results.club_revenge(m["home"], m["away"], m["kickoff_utc"], european,
                                                            elims, config["signals"]["revenge"]),
                  "european_meetings": meetings.get("-".join(str(i) for i in sorted(m["fd_ids"])))
                  if m.get("fd_ids") else None}
        ctx = context(m, results, tables, rivalries, config, extras)
        extras["tier1"] = bool(ctx["rivalry"]) and ctx["rivalry"]["tier"] == 1 and \
            config["must_watch"]["tier_1_rivalry_always"]
        result = score_match(ctx, config)
        kickoff = m["kickoff_utc"].astimezone(PARIS)
        ranked.append({"id": m["id"], "competition": m["competition"],
                       "kickoff_paris": kickoff.isoformat(), "day": kickoff.date().isoformat(),
                       "home": m["home"], "away": m["away"], **result,
                       "tier1_rivalry": bool(extras.get("tier1")), "espn": espn_link(m, espn_ids, us_tv)})

    # A competition with fixtures still to play but none in the window is suspicious
    # (a bad API response once dropped the whole Champions League without any error).
    in_window = {m["competition"] for m in ranked}
    for comp in sorted({m["competition"] for m in matches if m["status"] == "upcoming"} - in_window):
        nxt = min(m["kickoff_utc"] for m in matches if m["competition"] == comp and m["status"] == "upcoming")
        if nxt < end:
            warnings.append(f"{comp}: upcoming fixtures exist in the window but none were ranked")

    ranked.sort(key=sort_key)
    out = {"generated_at": now.astimezone(PARIS).isoformat(), "window_days": config["window_days"],
           "favourites": config["favourites"]["teams"], "favourite_boost": config["favourites"]["boost"],
           "must_watch_threshold": config["must_watch"]["score_threshold"],
           "recommended_threshold": config["must_watch"]["recommended_threshold"],
           "scale_reference": config["scale"]["reference"],
           "weights": {k: v for k, v in config["weights"].items() if v},
           "matches": ranked, "warnings": warnings,
           "unmatched_teams": sorted(registry.unmatched)}
    (OUTPUT / "matches_ranked.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    write_results(matches, espn_ids, us_tv, registry, now)
    return out


def add_other_clubs(clubs, path, matches):
    """Stature for clubs outside our 7 leagues (Bodø/Glimt, Ferencváros…), matched by name."""
    if not path.exists():
        return
    index = {}
    for other in json.loads(path.read_text(encoding="utf-8")).get("others", []):
        for name in other["names"]:
            index.setdefault(name, other)
    for team in {t for m in matches for t in (m["home"], m["away"])} - set(clubs):
        hit = index.get(norm(team))
        if hit:
            clubs[team] = {k: hit[k] for k in ("points", "rank", "uefa_name")}


def add_team_forms(results, registry):
    """Domestic results of European opponents outside our leagues (fetch_team_forms.py)."""
    path = OUTPUT / "team_forms.json"
    if not path.exists():
        return
    for tid, club in json.loads(path.read_text(encoding="utf-8")).items():
        team = registry.from_espn(tid, club["name"])
        rows = results.setdefault(team, [])
        days = {r["kickoff_utc"].date() for r in rows}
        for m in club["matches"]:
            kickoff = datetime.fromisoformat(m["date"].replace("Z", "+00:00"))
            if kickoff.date() in days:
                continue  # a European game we already have
            rows.append({"competition": m.get("league") or "Domestic", "kickoff_utc": kickoff, "opponent": m["opponent"],
                         "gf": m["gf"], "ga": m["ga"], "points": 3 if m["gf"] > m["ga"] else 1 if m["gf"] == m["ga"] else 0})
        rows.sort(key=lambda r: r["kickoff_utc"])


def search_aliases(registry):
    """Every name a club goes by (teams.csv aliases, football-data.org names), for the search bar."""
    names = {}
    for alias_norm, key in registry.by_name.items():
        names.setdefault(key, set()).add(alias_norm)
    return {k: " ".join(sorted(v)) for k, v in names.items()}


def write_results(matches, espn_ids, us_tv, registry, now):
    """Finished matches this season, newest first, for the Results tab."""
    rows = []
    for m in matches:
        if m["status"] != "finished" or m["home_goals"] is None:
            continue
        kickoff = m["kickoff_utc"].astimezone(PARIS)
        rows.append({"id": m["id"], "competition": m["competition"], "kickoff_paris": kickoff.isoformat(),
                     "day": kickoff.date().isoformat(), "home": m["home"], "away": m["away"],
                     "home_goals": m["home_goals"], "away_goals": m["away_goals"],
                     "espn": espn_link(m, espn_ids, us_tv)})
    rows.sort(key=lambda r: r["kickoff_paris"], reverse=True)
    teams_seen = {t for r in rows for t in (r["home"], r["away"])}
    aliases = {k: v for k, v in search_aliases(registry).items() if k in teams_seen}
    out = {"generated_at": now.astimezone(PARIS).isoformat(), "matches": rows, "aliases": aliases}
    (OUTPUT / "results.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    out = build()
    print(f"{len(out['matches'])} matches ranked, {sum(m['must_watch'] for m in out['matches'])} must-watch")
    counts = {}
    for m in out["matches"]:
        counts[m["competition"]] = counts.get(m["competition"], 0) + 1
    print("  per competition:", ", ".join(f"{c} {n}" for c, n in sorted(counts.items())))
    for m in out["matches"][:15]:
        print(f"{m['score']:3} {'*' if m['must_watch'] else ' '} {m['day']} {m['competition'][:16]:16} "
              f"{m['home']} v {m['away']}  | {m['story']}")
    for w in out["warnings"]:
        print("WARNING:", w, file=sys.stderr)
    if out["unmatched_teams"]:
        print(f"{len(out['unmatched_teams'])} team names not in teams.csv (logged in the output)", file=sys.stderr)
