from datetime import datetime, timedelta, timezone

import pytest

from scrape_europe import parse
from score import context, ordinal, score_match, signal_stakes
from stats import form, streaks, team_results

T0 = datetime(2026, 10, 1, 18, tzinfo=timezone.utc)
KICKOFF = datetime(2026, 10, 25, 18, tzinfo=timezone.utc)


def played(home, away, hg, ag, days, comp="Premier League"):
    return {"id": f"{home}-{away}-{days}", "competition": comp, "stage": "REGULAR_SEASON",
            "kickoff_utc": T0 + timedelta(days=days), "home": home, "away": away,
            "status": "finished", "home_goals": hg, "away_goals": ag}


def fixture(home, away, comp="Premier League", stage="REGULAR_SEASON"):
    return {"id": "x", "competition": comp, "stage": stage, "kickoff_utc": KICKOFF,
            "home": home, "away": away, "status": "upcoming", "home_goals": None, "away_goals": None}


def table(points, played=19):
    """A 20-team table from a points list, best first."""
    return [{"team": f"T{i + 1}", "position": i + 1, "played": played, "points": p} for i, p in enumerate(points)]


FLAT = [60, 58, 55, 50, 48, 46, 44, 42, 40, 38, 36, 34, 32, 30, 28, 26, 24, 22, 20, 18]


# --- stats ---

def test_form_counts_last_n_before_kickoff():
    ms = [played("A", "B", 2, 0, d) for d in range(6)] + [played("B", "A", 3, 0, 10)]
    res = team_results(ms)
    f = form(res["A"], KICKOFF, 5)
    assert f["games"] == 5 and f["wins"] == 4
    assert f["ppg"] == pytest.approx(12 / 5)
    assert f["goals_per_game"] == pytest.approx(11 / 5)
    # Matches after the kickoff never leak in.
    assert form(res["A"], T0 + timedelta(days=3), 5)["games"] == 3


def test_streaks_win_and_unbeaten():
    ms = [played("A", "X", 0, 1, 0), played("A", "X", 1, 0, 1), played("A", "X", 1, 1, 2),
          played("A", "X", 2, 0, 3), played("A", "X", 3, 0, 4)]
    assert streaks(team_results(ms)["A"]) == {"win": 2, "unbeaten": 4}


# --- signals ---

def test_title_race_both_teams(config):
    cfg = config["signals"]["stakes"]
    ctx = {**fixture("T1", "T2"), "table": table(FLAT)}
    value, story = signal_stakes(ctx, cfg)
    assert value == pytest.approx(1.0)  # 19 of 38 games played: past the damping point
    assert story == ("stakes_title", {"gap": 2})


def test_relegation_battle(config):
    ctx = {**fixture("T18", "T19"), "table": table(FLAT)}
    value, story = signal_stakes(ctx, config["signals"]["stakes"])
    assert value == pytest.approx(1.0) and story[0] == "stakes_relegation"


def test_mid_table_has_no_stakes(config):
    ctx = {**fixture("T11", "T12"), "table": table(FLAT)}
    assert signal_stakes(ctx, config["signals"]["stakes"]) == (0.0, None)


def test_early_season_damping(config):
    cfg = config["signals"]["stakes"]
    ctx = {**fixture("T1", "T2"), "table": table(FLAT, played=4)}
    value, _ = signal_stakes(ctx, cfg)
    assert value == pytest.approx(max(cfg["min_factor"], (4 / 38) / cfg["full_weight_from_share"]))


def test_knockout(config):
    ctx = {**fixture("A", "B", comp="Champions League", stage="LAST_16"), "table": None}
    assert signal_stakes(ctx, config["signals"]["stakes"]) == (1.0, ("stakes_knockout", {}))


def test_missing_table_scores_zero(config):
    ctx = {**fixture("A", "B"), "table": None}
    assert signal_stakes(ctx, config["signals"]["stakes"]) == (0.0, None)


# --- whole match ---

def history(goals_a=3, goals_b=2):
    ms = []
    for d in range(5):
        ms.append(played("T1", "Z", goals_a, 0, d))
        ms.append(played("T2", "Z", goals_b, 1, d))
    return team_results(ms)


def test_full_score_story_and_breakdown(config):
    rivalries = {frozenset(("T1", "T2")): {"tier": 2, "rivalry_name": "The Test Derby"}}
    ctx = context(fixture("T1", "T2"), history(), {"Premier League": table(FLAT)}, rivalries, config)
    r = score_match(ctx, config)
    b = r["breakdown"]
    # form: both teams won 5/5 -> ppg 3 -> min(1, 1 + bonus)
    assert b["form"]["value"] == 1.0
    # entertainment: (3 + 3) / 2 = 3 goals per game / 4
    assert b["entertainment"]["value"] == pytest.approx(0.75)
    assert b["rivalry"]["value"] == 0.6
    assert r["score"] == round(sum(x["points"] for x in b.values()))
    parts = r["story"].split(config["story"]["separator"])
    assert len(parts) == config["story"]["max_reasons"]
    assert parts[0] == "Both teams in form"  # biggest contribution first
    assert not r["must_watch"] or r["score"] >= config["must_watch"]["score_threshold"]


def test_missing_data_gives_zero_and_no_reason(config):
    ctx = context(fixture("New1", "New2"), {}, {}, {}, config)
    r = score_match(ctx, config)
    assert r["score"] == 0 and r["story"] == ""
    assert all("reason" not in b for b in r["breakdown"].values())


def test_tier1_rivalry_is_must_watch(config):
    rivalries = {frozenset(("New1", "New2")): {"tier": 1, "rivalry_name": "Big One"}}
    r = score_match(context(fixture("New1", "New2"), {}, {}, rivalries, config), config)
    assert r["must_watch"] and r["story"] == "Big One"


def test_favourite_boost_bonus_and_cap(config):
    config["favourites"]["teams"] = ["T1"]
    rivalries = {frozenset(("T1", "T2")): {"tier": 1, "rivalry_name": "Big One"}}
    ctx = context(fixture("T1", "T2", comp="Champions League"), history(6, 6), {}, rivalries, config)
    r = score_match(ctx, config)
    assert r["favourite"] and r["favourite_boost"] == 15 and r["competition_bonus"] == 5
    assert r["score"] == min(100, round(r["base"] + 20))


def test_closeness_reason_only_when_close(config):
    tables = {"Premier League": table(FLAT)}
    far = score_match(context(fixture("T1", "T20"), history(), tables, {}, config), config)
    assert "reason" not in far["breakdown"]["closeness"]


# --- helpers ---

def test_ordinal():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22)] == \
        ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd"]


def test_espn_kickoff_converted_to_paris_across_dst():
    def event(i, when):
        return {"id": str(i), "date": when, "status": {"type": {"name": "STATUS_SCHEDULED"}},
                "competitions": [{"competitors": [
                    {"homeAway": "home", "team": {"id": "1", "displayName": "Home"}, "score": "0"},
                    {"homeAway": "away", "team": {"id": "2", "displayName": "Away"}, "score": "0"}]}]}
    rows = parse({"events": [event(1, "2026-10-22T16:45Z"), event(2, "2026-11-05T17:45Z")]}, "Europa League")
    assert rows[0]["kickoff_paris"] == "2026-10-22T18:45:00+02:00"  # summer time
    assert rows[1]["kickoff_paris"] == "2026-11-05T18:45:00+01:00"  # winter time
