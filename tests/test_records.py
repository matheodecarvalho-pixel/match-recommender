from datetime import datetime, timedelta, timezone

from records import _chase, team_chases, update_streaks
from score import signal_records
from stats import team_results

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


class FakeRegistry:
    def from_fd(self, team):
        return team["name"]


def scorer(pid, team, goals, assists=None):
    return {"player": {"id": pid, "name": f"Player {pid}"}, "team": {"id": 1, "name": team},
            "goals": goals, "assists": assists}


def test_streak_grows_resets_and_starts_unknown():
    reg = FakeRegistry()
    snap = update_streaks({}, [scorer(9, "A", 5)], {"A": 6}, reg)
    assert snap["9"]["streak"] is None  # first snapshot: unknown
    snap = update_streaks(snap, [scorer(9, "A", 5)], {"A": 7}, reg)
    assert snap["9"]["streak"] == 0  # team played, no goal
    snap = update_streaks(snap, [scorer(9, "A", 6)], {"A": 8}, reg)
    assert snap["9"]["streak"] == 1
    snap = update_streaks(snap, [scorer(9, "A", 6)], {"A": 8}, reg)
    assert snap["9"]["streak"] == 1  # team didn't play: unchanged
    snap = update_streaks(snap, [scorer(9, "A", 8)], {"A": 9}, reg)
    assert snap["9"]["streak"] == 2
    snap = update_streaks(snap, [scorer(9, "A", 9)], {"A": 11}, reg)
    assert snap["9"]["streak"] is None  # two games in between: can't tell
    snap = update_streaks(snap, [scorer(9, "A", 9)], {"A": 13}, reg)
    assert snap["9"]["streak"] == 0  # two games, no goals: surely over


def test_unknown_streak_stays_unknown_until_a_blank():
    reg = FakeRegistry()
    snap = update_streaks({}, [scorer(9, "A", 5)], {"A": 6}, reg)
    snap = update_streaks(snap, [scorer(9, "A", 6)], {"A": 7}, reg)
    assert snap["9"]["streak"] is None


def test_chase_distance_and_units():
    rec = {"value": 36, "unit": "goals", "record": "Most goals in a season"}
    c = _chase("A", "Premier League", "Erling Haaland", 35, rec)
    assert c["distance"] == 1 and c["story"]["unit"] == "goal"
    assert _chase("A", "Premier League", "X", 36, rec) is None  # equalled or broken: no chase
    rec = {"value": 11, "unit": "matches", "record": "Consecutive matches scored in"}
    assert _chase("A", "Premier League", "X", 8, rec)["story"]["unit"] == "matches"


def test_team_win_streak_chase_from_results():
    ms = [{"competition": "Bundesliga", "kickoff_utc": T0 + timedelta(days=d), "home": "A", "away": "Z",
           "status": "finished", "home_goals": 2, "away_goals": 0} for d in range(16)]
    rec = {"subject": "team", "competition": "Bundesliga", "metric_to_track": "current win streak",
           "value": 19, "unit": "wins", "record": "Most consecutive wins"}
    chases = [c for c in team_chases([rec], team_results(ms)) if c["team"] == "A"]
    assert chases[0]["distance"] == 3


def test_records_signal_picks_closest(config):
    cfg = config["signals"]["records"]
    ctx = {"record_chases": [{"distance": 4, "story": {"x": 1}}, {"distance": 1, "story": {"y": 2}}]}
    assert signal_records(ctx, cfg) == (cfg["within_1"], ("records", {"y": 2}))
    assert signal_records({"record_chases": [{"distance": 9, "story": {}}]}, cfg) == (0.0, None)
