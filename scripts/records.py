"""Record chases: how far a team or player is from a record in data/records.json.

Tracked (free data only):
  team   current win streak / unbeaten run   from results, league matches only
  team   season points / goals               from results, league matches only
  player season goals / assists              football-data.org scorers
  player current scoring streak              scorers diff against the previous run

Not tracked (no free source): clean sheets, minutes without conceding, fewest goals
conceded, career totals, titles. Those records never score.

Distance is always record value minus current value, never a projection. Only chases
with a distance of 1 or more are returned (a broken record is not a chase).
"""
import json

from fd_client import COMPETITIONS
from stats import streaks

CODES = {name: code for code, name in COMPETITIONS.items()}
SINGULAR = {"goals": "goal", "assists": "assist", "matches": "match", "wins": "win", "points": "point"}


def _chase(team, competition, holder, current, rec):
    distance = rec["value"] - current
    if distance < 1:
        return None
    unit = rec["unit"] if distance != 1 else SINGULAR.get(rec["unit"], rec["unit"])
    return {"team": team, "competition": competition, "distance": distance,
            "story": {"player": holder, "distance": distance, "unit": unit,
                      "competition": competition, "record": rec["record"].lower()}}


def _team_value(metric, rows, competition):
    league = [r for r in rows if r["competition"] == competition]
    if not league:
        return None
    if metric == "current win streak":
        return streaks(league)["win"]
    if metric == "current unbeaten run":
        return streaks(league)["unbeaten"]
    if metric == "season points pace":
        return sum(r["points"] for r in league)
    if metric == "season goals pace":
        return sum(r["gf"] for r in league)
    return None


def team_chases(records, results):
    chases = []
    for rec in records:
        if rec["subject"] != "team" or rec["competition"] not in CODES:
            continue
        for team, rows in results.items():
            current = _team_value(rec["metric_to_track"], rows, rec["competition"])
            if current is not None:
                c = _chase(team, rec["competition"], team, current, rec)
                if c:
                    chases.append(c)
    return chases


def team_games(matches, competition):
    games = {}
    for m in matches:
        if m["competition"] == competition and m["status"] == "finished":
            for side in ("home", "away"):
                games[m[side]] = games.get(m[side], 0) + 1
    return games


def update_streaks(previous, scorers, games, registry):
    """New scorer snapshot with scoring streaks carried over from the previous one.

    For each player: if his team played exactly one game since the last snapshot,
    the streak goes up when his goal total rose and resets to 0 when it didn't.
    With two or more games in between we can't tell which games he scored in,
    so the streak becomes unknown (None). The first snapshot starts at unknown.
    """
    snapshot = {}
    for s in scorers:
        pid = str(s["player"]["id"])
        team = registry.from_fd(s["team"])
        played = games.get(team, 0)
        goals = s.get("goals") or 0
        old = previous.get(pid)
        streak = None
        if old and old["team"] == team:
            new_games = played - old["team_games"]
            if new_games == 0:
                streak = old["streak"]
            elif new_games == 1:
                streak = (old["streak"] or 0) + 1 if goals > old["goals"] else 0
                if goals > old["goals"] and old["streak"] is None:
                    streak = None  # rose, but we never knew the start of the run
            elif goals == old["goals"]:
                streak = 0  # several games, no goals: the run is over for sure
        snapshot[pid] = {"name": s["player"]["name"], "team": team, "goals": goals,
                         "team_games": played, "streak": streak}
    return snapshot


def player_chases(records, root, matches, registry, warnings, save=True):
    raw = root / "output" / "raw" / "fd"
    history = root / "output" / "scorers_history"
    chases = []
    for competition, code in CODES.items():
        path = raw / f"{code}_scorers.json"
        if not path.exists():
            continue
        scorers = json.loads(path.read_text(encoding="utf-8"))["scorers"]
        snap_path = history / f"{code}.json"
        previous = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.exists() else {}
        snapshot = update_streaks(previous, scorers, team_games(matches, competition), registry)
        if save:
            history.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")

        for rec in records:
            if rec["subject"] != "player" or rec["competition"] != competition:
                continue
            metric = rec["metric_to_track"]
            for s in scorers:
                pid, name = str(s["player"]["id"]), s["player"]["name"]
                team = registry.from_fd(s["team"])
                if metric in ("season goals", "season UCL goals"):
                    current = s.get("goals")
                elif metric == "season assists":
                    current = s.get("assists")
                elif metric in ("current scoring streak", "current UCL scoring streak"):
                    current = snapshot[pid]["streak"]
                else:
                    break  # metric we can't track
                if current is None:
                    continue
                c = _chase(team, competition, name, current, rec)
                if c:
                    chases.append(c)
    return chases


def track(root, matches, results, tables, registry, warnings, save=True):
    """{team: [chase, ...]}; each chase applies only to that team's matches in its competition."""
    records = json.loads((root / "data" / "records.json").read_text(encoding="utf-8"))
    out = {}
    for c in team_chases(records, results) + player_chases(records, root, matches, registry, warnings, save):
        out.setdefault(c["team"], []).append(c)
    return out
