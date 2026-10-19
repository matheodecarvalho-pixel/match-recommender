"""Load every match into one shape, then compute per-team stats.

A match: {id, competition, stage, kickoff_utc (datetime), home, away, status,
home_goals, away_goals}. status is "upcoming", "finished" or "other".
"""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fd_client import COMPETITIONS

PARIS = ZoneInfo("Europe/Paris")
FD_UPCOMING = {"SCHEDULED", "TIMED", "IN_PLAY", "PAUSED"}
LEAGUES = [name for code, name in COMPETITIONS.items() if code != "CL"]


def _utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


# Team key -> badge URL, filled while loading (football-data.org crests, ESPN logos).
CRESTS = {}
ESPN_LOGO = "https://a.espncdn.com/i/teamlogos/soccer/500/{}.png"


def load_fd(raw_dir, registry):
    """Matches and tables from football-data.org raw files."""
    matches, tables = [], {}
    for code, name in COMPETITIONS.items():
        path = raw_dir / f"{code}_matches.json"
        if not path.exists():
            continue
        for m in json.loads(path.read_text(encoding="utf-8"))["matches"]:
            if not m["homeTeam"].get("id") or not m["awayTeam"].get("id"):
                continue  # knockout slot not decided yet
            for side in ("homeTeam", "awayTeam"):
                if m[side].get("crest"):
                    CRESTS.setdefault(registry.from_fd(m[side]), m[side]["crest"])
            status = ("finished" if m["status"] == "FINISHED"
                      else "upcoming" if m["status"] in FD_UPCOMING else "other")
            full = m["score"]["fullTime"]
            matches.append({
                "id": f"fd-{m['id']}", "competition": name, "stage": m.get("stage"),
                "kickoff_utc": _utc(m["utcDate"]),
                "home": registry.from_fd(m["homeTeam"]), "away": registry.from_fd(m["awayTeam"]),
                "status": status, "home_goals": full.get("home"), "away_goals": full.get("away"),
                "fd_ids": (m["homeTeam"]["id"], m["awayTeam"]["id"])})
        spath = raw_dir / f"{code}_standings.json"
        if spath.exists():
            for s in json.loads(spath.read_text(encoding="utf-8"))["standings"]:
                if s["type"] == "TOTAL":
                    tables[name] = [{"team": registry.from_fd(r["team"]), "position": r["position"],
                                     "played": r["playedGames"], "points": r["points"]} for r in s["table"]]
    return matches, tables


def load_europe(path, registry):
    """Europa and Conference League matches and league-phase tables (scrape_europe.py output)."""
    if not path.exists():
        return [], {}, ["europe_matches.json missing: Europa/Conference League skipped"]
    data = json.loads(path.read_text(encoding="utf-8"))
    tables = {comp: [{"team": registry.from_espn(r["espn_id"], r["team"]), "position": r["position"],
                      "played": r["played"], "points": r["points"]} for r in rows]
              for comp, rows in data.get("standings", {}).items() if rows}
    matches = []
    for m in data["matches"]:
        for side in ("home", "away"):
            CRESTS.setdefault(registry.from_espn(m[f"{side}_espn_id"], m[side]), ESPN_LOGO.format(m[f"{side}_espn_id"]))
        status = {"finished": "finished", "scheduled": "upcoming", "live": "upcoming"}.get(m["status"], "other")
        matches.append({
            "id": f"espn-{m['id']}", "competition": m["competition"], "stage": m.get("stage"),
            "kickoff_utc": _utc(m["kickoff_utc"]),
            "home": registry.from_espn(m["home_espn_id"], m["home"]),
            "away": registry.from_espn(m["away_espn_id"], m["away"]),
            "status": status, "home_goals": m.get("home_goals"), "away_goals": m.get("away_goals")})
    return matches, tables, list(data.get("warnings", []))


def team_results(matches):
    """Each team's finished matches, oldest first, from its own point of view."""
    results = {}
    for m in sorted(matches, key=lambda m: m["kickoff_utc"]):
        if m["status"] != "finished" or m["home_goals"] is None:
            continue
        for side, other, gf, ga in (("home", "away", m["home_goals"], m["away_goals"]),
                                    ("away", "home", m["away_goals"], m["home_goals"])):
            results.setdefault(m[side], []).append({
                "competition": m["competition"], "kickoff_utc": m["kickoff_utc"], "opponent": m[other],
                "gf": gf, "ga": ga, "points": 3 if gf > ga else 1 if gf == ga else 0})
    return results


def form(results, before, n):
    """Last n results before a kickoff: ppg, wins, goals per game (scored + conceded)."""
    recent = [r for r in results if r["kickoff_utc"] < before][-n:]
    if not recent:
        return None
    games = len(recent)
    return {"games": games,
            "ppg": sum(r["points"] for r in recent) / games,
            "wins": sum(1 for r in recent if r["points"] == 3),
            "goals_per_game": sum(r["gf"] + r["ga"] for r in recent) / games}


def streaks(results, competition=None):
    """Current win and unbeaten streaks (newest backwards), optionally in one competition."""
    rows = [r for r in results if competition is None or r["competition"] == competition]
    win = unbeaten = 0
    for r in reversed(rows):
        if r["points"] == 3 and win == unbeaten:
            win += 1
        if r["points"] >= 1:
            unbeaten += 1
        else:
            break
    return {"win": win, "unbeaten": unbeaten}
