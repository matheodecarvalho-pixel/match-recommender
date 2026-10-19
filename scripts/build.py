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
from stats import CRESTS, PARIS, load_europe, load_fd, team_results

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


def load_inputs(now):
    """Everything scoring needs, loaded once: matches, tables, rivalries, revenge, stature, history."""
    config = json.loads((ROOT / "config" / "scoring.json").read_text(encoding="utf-8"))
    registry = teams.load(ROOT)
    STYLES.update(load_styles(registry))
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
    stature_path = ROOT / "data" / "club_stature.json"
    clubs = json.loads(stature_path.read_text(encoding="utf-8"))["clubs"] if stature_path.exists() else {}
    if not clubs:
        warnings.append("No club_stature.json: big-match signal scores 0")
    add_other_clubs(clubs, stature_path, matches)
    history_path = ROOT / "data" / "league_history.json"
    history = json.loads(history_path.read_text(encoding="utf-8"))["leagues"] if history_path.exists() else {}
    add_team_forms(results, registry)
    ids_path = OUTPUT / "espn_ids.json"
    europe_path = OUTPUT / "europe_matches.json"
    return {"config": config, "registry": registry, "matches": matches, "tables": tables, "eu_tables": eu_tables,
            "results": results, "rivalries": rivalries, "chases": chases, "moves": moves, "european": european,
            "elims": euro_results.eliminations(european), "meetings": euro_results.european_meetings(ROOT),
            "clubs": clubs, "history": history, "warnings": warnings,
            "espn_ids": json.loads(ids_path.read_text(encoding="utf-8")) if ids_path.exists() else {},
            "us_tv": {m["id"]: m.get("us_tv", []) for m in json.loads(europe_path.read_text(encoding="utf-8"))["matches"]}
            if europe_path.exists() else {}}


def score_fixture(m, inp, tables, knockout, chases=True):
    """Score one match against the given tables (today's, or rebuilt as they stood before kickoff)."""
    config = inp["config"]
    extras = {"knockout": m["competition"] in knockout, "stature": inp["clubs"], "history": inp["history"],
              "record_chases": [c for team in (m["home"], m["away"]) for c in inp["chases"].get(team, [])
                                if c["competition"] == m["competition"]] if chases else [],
              "revenge": inp["moves"].flags(m["home"], m["away"], m["kickoff_utc"]),
              "club_revenge": euro_results.club_revenge(m["home"], m["away"], m["kickoff_utc"], inp["european"],
                                                        inp["elims"], config["signals"]["revenge"]),
              "european_meetings": inp["meetings"].get("-".join(str(i) for i in sorted(m["fd_ids"])))
              if m.get("fd_ids") else None}
    ctx = context(m, inp["results"], tables, inp["rivalries"], config, extras)
    tier1 = bool(ctx["rivalry"]) and ctx["rivalry"]["tier"] == 1 and config["must_watch"]["tier_1_rivalry_always"]
    result = score_match(ctx, config)
    kickoff = m["kickoff_utc"].astimezone(PARIS)
    return {"id": m["id"], "competition": m["competition"],
            "kickoff_paris": kickoff.isoformat(), "day": kickoff.date().isoformat(),
            "home": m["home"], "away": m["away"], **result,
            "tier1_rivalry": tier1, "espn": espn_link(m, inp["espn_ids"], inp["us_tv"])}


def build(now=None):
    now = now or datetime.now(timezone.utc)
    inp = load_inputs(now)
    config, registry, matches, warnings = inp["config"], inp["registry"], inp["matches"], inp["warnings"]
    espn_ids, us_tv = inp["espn_ids"], inp["us_tv"]

    # After the 8 league-phase rounds, every Europa/Conference match is a knockout.
    knockout = {comp for comp, table in inp["eu_tables"].items() if table and min(r["played"] for r in table) >= 8}

    end = now + timedelta(days=config["window_days"])
    ranked = [score_fixture(m, inp, inp["tables"], knockout) for m in matches
              if m["status"] == "upcoming" and now - timedelta(hours=2) <= m["kickoff_utc"] < end]

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
           "crests": {t: CRESTS[t] for t in {x for m in ranked for x in (m["home"], m["away"])} if t in CRESTS},
           "styles": {t: v for t, v in STYLES.items() if t in {x for m in ranked for x in (m["home"], m["away"])}},
           "unmatched_teams": sorted(registry.unmatched)}
    (OUTPUT / "matches_ranked.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    archive = update_archive(ranked, now)
    added = reconstruct(archive, inp)
    if added:
        save_archive(archive)
        print(f"{added} past matches given a rebuilt pre-match score")
    write_results(matches, espn_ids, us_tv, registry, now, archive)
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


STYLES = {}


def load_styles(registry):
    """Team -> play style (data/play_styles.json), keyed by our team names, for chips and My Style."""
    path = ROOT / "data" / "play_styles.json"
    if not path.exists():
        return {}
    out = {}
    for name, c in json.loads(path.read_text(encoding="utf-8"))["clubs"].items():
        entry = {"style": c["profile"], "confidence": c["confidence"]}
        out[name] = entry
        # The style file uses ESPN's spelling for some clubs ("Slavia Prague", "C.D. Nacional").
        key = registry.by_name.get(norm(name))
        if key:
            out.setdefault(key, entry)
    return out


def search_aliases(registry):
    """Every name a club goes by (teams.csv aliases, football-data.org names), for the search bar."""
    names = {}
    for alias_norm, key in registry.by_name.items():
        names.setdefault(key, set()).add(alias_norm)
    return {k: " ".join(sorted(v)) for k, v in names.items()}


ARCHIVE = OUTPUT / "score_archive.json"


def frozen(m):
    """What the Results tab keeps of a match's pre-match score (enough to re-score with My Feed)."""
    return {"score": m["score"], "must_watch": m["must_watch"], "recommended": m.get("recommended", False),
            "story": m["story"], "base": m["base"], "competition_bonus": m["competition_bonus"],
            "stage_bonus": m.get("stage_bonus", 0), "tier1_rivalry": m.get("tier1_rivalry", False),
            "breakdown": {k: {"points": b["points"], **({"kind": b["kind"]} if "kind" in b else {})}
                          for k, b in m["breakdown"].items()}}


def update_archive(ranked, now):
    """Keep each match's latest pre-match score; once it has kicked off, the entry never changes."""
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else {}
    for m in ranked:
        if datetime.fromisoformat(m["kickoff_paris"]) > now:
            archive[m["id"]] = {**frozen(m), "frozen_at": now.astimezone(PARIS).isoformat()}
    save_archive(archive)
    return archive


def save_archive(archive):
    ARCHIVE.write_text(json.dumps(archive, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")


# The group that forms one table in each competition (European cups: league phase only).
# ESPN games cached before the stage was recorded have none; europe_matches.json holds only the league phase.
TABLE_STAGES = {"Champions League": {"LEAGUE_STAGE"}, "Europa League": {"league-phase", None},
                "Conference League": {"league-phase", None}}


def in_table(m):
    stages = TABLE_STAGES.get(m["competition"])
    return stages is None or m["stage"] in stages


def table_before(matches, competition, before, adjust=None):
    """A competition's table from its results before a kickoff: points, then goal difference, then goals.

    Head-to-head tie-breaks are ignored. `adjust` adds points the results don't explain (deductions).
    """
    rows = {}
    for m in matches:
        if m["competition"] != competition or not in_table(m):
            continue
        for side in ("home", "away"):
            rows.setdefault(m[side], {"team": m[side], "played": 0, "points": (adjust or {}).get(m[side], 0), "gd": 0, "gf": 0})
        if m["status"] != "finished" or m["home_goals"] is None or m["kickoff_utc"] >= before:
            continue
        for side, gf, ga in (("home", m["home_goals"], m["away_goals"]), ("away", m["away_goals"], m["home_goals"])):
            r = rows[m[side]]
            r["played"] += 1
            r["points"] += 3 if gf > ga else 1 if gf == ga else 0
            r["gd"] += gf - ga
            r["gf"] += gf
    table = sorted(rows.values(), key=lambda r: (-r["points"], -r["gd"], -r["gf"], r["team"]))
    return [{"team": r["team"], "position": i, "played": r["played"], "points": r["points"]}
            for i, r in enumerate(table, 1)]


def deductions(matches, tables, competition, now):
    """Points in the published table that the results don't explain (a sanction), per team."""
    rebuilt = {r["team"]: r for r in table_before(matches, competition, now)}
    out = {}
    for r in tables.get(competition) or []:
        mine = rebuilt.get(r["team"])
        if mine and mine["played"] == r["played"] and mine["points"] != r["points"]:
            out[r["team"]] = r["points"] - mine["points"]
    return out


def reconstruct(archive, inp, now=None):
    """Give every finished match without a frozen score one rebuilt from the data as it stood before kickoff.

    Form, goals, tables, revenge and European history are all cut at the kickoff. Club stature and the
    5-season league history are today's (they barely move within a season). Marked "reconstructed".
    """
    now = now or datetime.now(timezone.utc)
    matches = inp["matches"]
    comps = {m["competition"] for m in matches}
    adjust = {c: deductions(matches, inp["tables"], c, now) for c in comps}
    added = 0
    for m in matches:
        if m["status"] != "finished" or m["home_goals"] is None or m["id"] in archive:
            continue
        tables = {c: table_before(matches, c, m["kickoff_utc"], adjust[c]) for c in comps}
        if not in_table(m):
            tables.pop(m["competition"], None)  # a qualifier or play-off: no table to read
        knockout = {c for c in TABLE_STAGES if c != "Champions League" and tables.get(c)
                    and min(r["played"] for r in tables[c]) >= 8}
        scored = score_fixture(m, inp, tables, knockout, chases=False)
        archive[m["id"]] = {**frozen(scored), "frozen_at": m["kickoff_utc"].astimezone(PARIS).isoformat(),
                            "reconstructed": True}
        added += 1
    return added


def write_results(matches, espn_ids, us_tv, registry, now, archive=None):
    """Finished matches this season, newest first, for the Results tab."""
    rows = []
    for m in matches:
        if m["status"] != "finished" or m["home_goals"] is None:
            continue
        kickoff = m["kickoff_utc"].astimezone(PARIS)
        rows.append({"id": m["id"], "competition": m["competition"], "kickoff_paris": kickoff.isoformat(),
                     "day": kickoff.date().isoformat(), "home": m["home"], "away": m["away"],
                     "home_goals": m["home_goals"], "away_goals": m["away_goals"],
                     "espn": espn_link(m, espn_ids, us_tv),
                     "interest": (archive or {}).get(m["id"])})
    rows.sort(key=lambda r: r["kickoff_paris"], reverse=True)
    teams_seen = {t for r in rows for t in (r["home"], r["away"])}
    aliases = {k: v for k, v in search_aliases(registry).items() if k in teams_seen}
    out = {"generated_at": now.astimezone(PARIS).isoformat(), "matches": rows, "aliases": aliases,
           "crests": {t: CRESTS[t] for t in teams_seen if t in CRESTS},
           "styles": {t: v for t, v in STYLES.items() if t in teams_seen}}
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
