"""European results over the past year: club revenge and European classics.

Sources (all already on disk):
  output/raw/fd/CL_matches.json              this season's Champions League
  output/history/fd_CL_<season>.json         last season's Champions League
  output/europe_matches.json                 Europa/Conference League, this season ("matches")
                                             and the past 13 months ("history")
  output/h2h_cache.json                      European meetings since 2020 for upcoming CL pairs
"""
import json
from datetime import datetime, timezone

from revenge import months_before

# Knockout rounds, from both providers' stage names, in the words a story uses.
KNOCKOUT = {
    "PLAYOFFS": "knockout play-offs", "LAST_16": "round of 16", "QUARTER_FINALS": "quarter-finals",
    "SEMI_FINALS": "semi-finals", "FINAL": "final",
    "knockout-round-playoffs": "knockout play-offs", "round-of-16": "round of 16",
    "quarterfinals": "quarter-finals", "semifinals": "semi-finals", "final": "final",
}
FD_WINNER = {"HOME_TEAM": "home", "AWAY_TEAM": "away"}


def _utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _fd(matches, season, registry):
    out = []
    for m in matches:
        if m["status"] != "FINISHED":
            continue
        full = m["score"]["fullTime"]
        out.append({"competition": "Champions League", "season": season, "stage": m.get("stage"),
                    "kickoff_utc": _utc(m["utcDate"]),
                    "home": registry.from_fd(m["homeTeam"]), "away": registry.from_fd(m["awayTeam"]),
                    "home_goals": full.get("home"), "away_goals": full.get("away"),
                    "winner": FD_WINNER.get(m["score"].get("winner"))})
    return out


def _espn(matches, registry):
    out = []
    for m in matches:
        if m["status"] != "finished":
            continue
        winner = m.get("winner")
        if winner is None and m["home_goals"] != m["away_goals"]:
            winner = "home" if m["home_goals"] > m["away_goals"] else "away"
        out.append({"competition": m["competition"], "season": m.get("season"), "stage": m.get("stage"),
                    "kickoff_utc": _utc(m["kickoff_utc"]),
                    "home": registry.from_espn(m["home_espn_id"], m["home"]),
                    "away": registry.from_espn(m["away_espn_id"], m["away"]),
                    "home_goals": m["home_goals"], "away_goals": m["away_goals"], "winner": winner})
    return out


def load(root, registry):
    """Every finished European match we have, oldest first, one row per match."""
    out = []
    raw = root / "output" / "raw" / "fd" / "CL_matches.json"
    if raw.exists():
        data = json.loads(raw.read_text(encoding="utf-8"))
        out += _fd(data["matches"], int(data["filters"]["season"]), registry)
    for path in sorted((root / "output" / "history").glob("fd_CL_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out += _fd(data["matches"], data["season"], registry)
    europe = root / "output" / "europe_matches.json"
    if europe.exists():
        data = json.loads(europe.read_text(encoding="utf-8"))
        seen, rows = set(), []
        for m in data.get("history", []) + data["matches"]:
            if m["id"] not in seen:
                seen.add(m["id"])
                rows.append(m)
        out += _espn(rows, registry)
    return sorted(out, key=lambda m: m["kickoff_utc"])


def eliminations(results):
    """Knockout ties that are settled: {winner, loser, competition, stage, kickoff_utc}.

    The side that goes through is the one that plays a later knockout round of the same
    competition and season; in a final it is the match winner. Ties still in progress
    (nobody has played a later round yet) are left out.
    """
    ties = {}
    for m in results:
        if m["stage"] in KNOCKOUT:
            key = (m["competition"], m["season"], m["stage"], frozenset((m["home"], m["away"])))
            ties.setdefault(key, []).append(m)
    out = []
    for (comp, season, stage, pair), legs in ties.items():
        last = max(legs, key=lambda m: m["kickoff_utc"])
        if KNOCKOUT[stage] == "final":
            winner = last[last["winner"]] if last["winner"] else None
        else:
            later = {t for m in results
                     if m["competition"] == comp and m["season"] == season and m["stage"] in KNOCKOUT
                     and m["kickoff_utc"] > last["kickoff_utc"] for t in (m["home"], m["away"])}
            through = [t for t in pair if t in later]
            winner = through[0] if len(through) == 1 else None
        if winner:
            loser = next(t for t in pair if t != winner)
            out.append({"winner": winner, "loser": loser, "competition": comp,
                        "stage": KNOCKOUT[stage], "kickoff_utc": last["kickoff_utc"]})
    return out


def club_revenge(home, away, kickoff, results, elims, cfg):
    """Revenge flags for one fixture: knocked out by, or lost to, today's opponent within the window."""
    start = months_before(kickoff.date(), cfg["club_window_months"])
    in_window = lambda m: start <= m["kickoff_utc"].date() and m["kickoff_utc"] < kickoff
    pair = {home, away}
    when = lambda m: m["kickoff_utc"].strftime("%B %Y")

    knocked = [e for e in elims if {e["winner"], e["loser"]} == pair and in_window(e)]
    if knocked:
        e = knocked[-1]
        return [{"value": cfg["club_knockout"], "story": ("revenge_knockout", {
            "loser": e["loser"], "winner": e["winner"], "competition": e["competition"],
            "stage": e["stage"], "when": when(e)})}]

    losses = [m for m in results if {m["home"], m["away"]} == pair and m["winner"] and in_window(m)]
    if losses:
        m = losses[-1]
        winner, loser = (m["home"], m["away"]) if m["winner"] == "home" else (m["away"], m["home"])
        goals = sorted((m["home_goals"], m["away_goals"]), reverse=True)
        return [{"value": cfg["club_loss"], "story": ("revenge_loss", {
            "loser": loser, "winner": winner, "competition": m["competition"],
            "score": f"{goals[0]}-{goals[1]}", "when": when(m)})}]
    return []


def european_meetings(root):
    """{(fd id, fd id) sorted: number of European meetings} from the head-to-head cache."""
    path = root / "output" / "h2h_cache.json"
    if not path.exists():
        return {}
    cache = json.loads(path.read_text(encoding="utf-8"))
    return {key: len(v["meetings"]) for key, v in cache.items()}
