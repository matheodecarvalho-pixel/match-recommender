from datetime import datetime, timedelta, timezone

from euro_results import club_revenge, eliminations
from score import signal_revenge, signal_rivalry

T0 = datetime(2026, 3, 1, 20, tzinfo=timezone.utc)
KICKOFF = datetime(2026, 10, 20, 19, tzinfo=timezone.utc)


def game(home, away, hg, ag, days, stage, comp="Champions League", season=2025, winner="auto"):
    if winner == "auto":
        winner = "home" if hg > ag else "away" if ag > hg else None
    return {"competition": comp, "season": season, "stage": stage, "kickoff_utc": T0 + timedelta(days=days),
            "home": home, "away": away, "home_goals": hg, "away_goals": ag, "winner": winner}


SEASON = [
    game("Bayern", "PSG", 1, 2, 60, "SEMI_FINALS"),
    game("PSG", "Bayern", 1, 1, 67, "SEMI_FINALS"),
    game("Arsenal", "Atleti", 1, 0, 60, "SEMI_FINALS"),
    game("Atleti", "Arsenal", 0, 0, 67, "SEMI_FINALS"),
    game("PSG", "Arsenal", 1, 1, 90, "FINAL", winner="home"),  # won on penalties
    game("Inter", "Bayern", 0, 2, 10, "LEAGUE_STAGE"),
]


def cfg():
    return {"club_window_months": 12, "club_knockout": 1.0, "club_loss": 0.5, "player": 1.0, "manager": 0.8}


def test_eliminations_from_later_round_and_final():
    out = {(e["winner"], e["loser"], e["stage"]) for e in eliminations(SEASON)}
    assert out == {("PSG", "Bayern", "semi-finals"), ("Arsenal", "Atleti", "semi-finals"),
                   ("PSG", "Arsenal", "final")}


def test_tie_in_progress_is_not_an_elimination():
    first_leg_only = [game("Real", "City", 2, 1, 0, "LAST_16")]
    assert eliminations(first_leg_only) == []


def test_knockout_revenge_beats_a_single_loss():
    flags = club_revenge("Bayern", "PSG", KICKOFF, SEASON, eliminations(SEASON), cfg())
    assert flags[0]["value"] == 1.0
    key, values = flags[0]["story"]
    assert key == "revenge_knockout"
    assert values["loser"] == "Bayern" and values["winner"] == "PSG" and values["when"] == "May 2026"


def test_single_loss_revenge():
    flags = club_revenge("Inter", "Bayern", KICKOFF, SEASON, eliminations(SEASON), cfg())
    assert flags[0]["value"] == 0.5
    assert flags[0]["story"] == ("revenge_loss", {"loser": "Inter", "winner": "Bayern",
                                                  "competition": "Champions League",
                                                  "score": "2-0", "when": "March 2026"})


def test_revenge_window_expires():
    later = KICKOFF + timedelta(days=365)
    assert club_revenge("Bayern", "PSG", later, SEASON, eliminations(SEASON), cfg()) == []


def test_draws_and_unrelated_pairs_give_nothing():
    assert club_revenge("PSG", "Inter", KICKOFF, SEASON, eliminations(SEASON), cfg()) == []


def test_revenge_signal_prefers_club_story_on_a_tie():
    ctx = {"revenge": [{"role": "player", "person": "X"}],
           "club_revenge": [{"value": 1.0, "story": ("revenge_knockout", {"a": 1})}]}
    assert signal_revenge(ctx, cfg()) == (1.0, ("revenge_knockout", {"a": 1}))
    ctx["club_revenge"][0]["value"] = 0.5
    assert signal_revenge(ctx, cfg()) == (1.0, ("revenge", {"person": "X", "team": None}))


def test_european_classic_needs_enough_meetings(config):
    rc = config["signals"]["rivalry"]
    ctx = {"rivalry": None, "european_meetings": 5}
    assert signal_rivalry(ctx, rc) == (0.6, ("european_classic", {"n": 5, "since": "2020"}))
    assert signal_rivalry({"rivalry": None, "european_meetings": 4}, rc) == (0.0, None)
    # A listed rivalry at least as strong keeps its own name.
    listed = {"tier": 2, "rivalry_name": "PSG v Barça"}
    assert signal_rivalry({"rivalry": listed, "european_meetings": 7}, rc)[1] == ("rivalry", {"rivalry_name": "PSG v Barça"})
