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
    assert story == ("stakes_title", {"gap": 2, "_quiet": False})


def test_relegation_battle(config):
    ctx = {**fixture("T18", "T19"), "table": table(FLAT)}
    value, story = signal_stakes(ctx, config["signals"]["stakes"])
    assert value == pytest.approx(1.0) and story[0] == "stakes_relegation"


def test_mid_table_has_no_stakes(config):
    ctx = {**fixture("T11", "T12"), "table": table(FLAT)}
    assert signal_stakes(ctx, config["signals"]["stakes"]) == (0.0, None)


def test_compressed_table_needs_places_too(config):
    # La Liga, October 2026: 7th has 11 pts, Rayo (14th) and Getafe (15th) have 8, the drop starts at 7.
    # Three points from Europe but seven places away: that is a relegation scrap, not a fight for Europe.
    pts = [27, 22, 19, 18, 16, 14, 11, 11, 11, 11, 9, 9, 8, 8, 8, 8, 7, 7, 6, 4]
    ctx = {**fixture("T15", "T14", comp="La Liga"), "table": table(pts, played=9)}
    _, story = signal_stakes(ctx, config["signals"]["stakes"])
    assert story[0] == "stakes_relegation"


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
    assert r["score"] == min(100, round(100 * sum(x["points"] for x in b.values()) / config["scale"]["reference"]))
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


def test_favourite_flag_bonus_and_cap(config):
    config["favourites"]["teams"] = ["T1"]
    rivalries = {frozenset(("T1", "T2")): {"tier": 1, "rivalry_name": "Big One"}}
    ctx = context(fixture("T1", "T2", comp="Champions League"), history(6, 6), {}, rivalries, config)
    r = score_match(ctx, config)
    assert r["favourite"] and r["favourite_boost"] == config["favourites"]["boost"] and r["competition_bonus"] == 5
    raw = r["base"] + r["competition_bonus"] + r["stage_bonus"]
    assert r["score"] == min(100, round(100 * raw / config["scale"]["reference"]) + r["favourite_boost"])


def test_knockout_round_bonus(config):
    ctx = context(fixture("A", "B", comp="Champions League", stage="SEMI_FINALS"), {}, {}, {}, config)
    assert score_match(ctx, config)["stage_bonus"] == config["knockout_bonus"]["semi_finals"]
    ctx = context(fixture("A", "B", comp="Europa League", stage="final"), {}, {}, {}, config)
    assert score_match(ctx, config)["stage_bonus"] == config["knockout_bonus"]["final"]


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


# --- big match and giant in trouble ---

from score import signal_big_match, signal_par

CLUBS = {"Giant": {"points": 100, "rank": 3}, "Big": {"points": 64, "rank": 20}, "Small": {"points": 4, "rank": 300}}


def test_big_match_is_the_product_of_statures(config):
    cfg = config["signals"]["big_match"]
    value, story = signal_big_match({"home": "Giant", "away": "Big", "stature": CLUBS}, cfg)
    assert value == pytest.approx(0.8) and story[0] == "big_match"
    value, story = signal_big_match({"home": "Giant", "away": "Small", "stature": CLUBS}, cfg)
    assert value == pytest.approx(0.2) and story is None
    assert signal_big_match({"home": "X", "away": "Y", "stature": CLUBS}, cfg) == (0.0, None)


def par_ctx(position, points, history, leader=30):
    rows = [{"team": f"T{i}", "position": i, "played": 10, "points": leader - i} for i in range(1, 21)]
    rows = [r for r in rows if r["position"] != position] + [{"team": "Club", "position": position, "played": 10, "points": points}]
    rows[0]["points"] = leader
    return {"home": "Club", "away": "T5", "domestic": {"Club": ("Premier League", rows)},
            "history": {"Premier League": {str(y): {"Club": p} for y, p in zip(range(2021, 2026), history)}}}


def test_under_par(config):
    cfg = config["signals"]["par"]
    value, story = signal_par(par_ctx(17, 10, [4, 8, 5, 6, 7]), cfg)  # usually 6th, now 17th
    assert value == 1.0 and story[0] == "par_under"
    assert story[1]["pos"] == "17th" and story[1]["usual"] == "6th"


def test_punching_above_their_weight(config):
    cfg = config["signals"]["par"]
    value, story = signal_par(par_ctx(3, 25, [8, 9, 8, 7, 8]), cfg)  # usually 8th, now 3rd
    assert value == pytest.approx((5 - cfg["places_start"]) / (cfg["places_full"] - cfg["places_start"]))
    assert story[0] == "par_over"


def test_par_needs_enough_seasons_and_distance(config):
    cfg = config["signals"]["par"]
    assert signal_par(par_ctx(17, 10, [6, 6]), cfg) == (0.0, None)  # only 2 seasons
    assert signal_par(par_ctx(7, 20, [6, 6, 6, 6, 6]), cfg)[0] == 0.0  # one place off: normal


def test_title_regular_far_off_the_top(config):
    cfg = config["signals"]["par"]
    value, story = signal_par(par_ctx(3, 21, [1, 2, 1, 2, 2]), cfg)  # usually 2nd, 9 pts behind
    assert value == pytest.approx((9 - cfg["gap_start"]) / (cfg["gap_full"] - cfg["gap_start"]))
    assert story[0] == "giant_gap" and story[1]["gap"] == 9


def test_story_is_split_by_team(config):
    from score import split_reason
    templates = config["story"]["side_templates"]
    ctx = {"home": "Monza", "away": "Cagliari"}
    form = split_reason("form", {"home": "Monza", "away": "Cagliari", "home_wins": 3, "away_wins": 1, "n": 5},
                        "x", ctx, templates)
    assert form == [("home", "Won 3 of last 5"), ("away", "Won 1 of last 5")]
    par = split_reason("par_over", {"team": "Cagliari", "pos": "7th", "usual": "16th", "league": "Serie A"}, "x", ctx, templates)
    assert par == [("away", "Usually finish 16th: punching above their weight")]
    assert split_reason("closeness", {}, "Evenly matched", ctx, templates) == [("both", "Evenly matched")]
