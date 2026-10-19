from datetime import datetime, timedelta, timezone

from build import deductions, table_before

T0 = datetime(2026, 9, 1, 18, tzinfo=timezone.utc)


def game(home, away, hg, ag, days, status="finished", comp="Ligue 1", stage="REGULAR_SEASON"):
    return {"id": f"{home}-{away}-{days}", "competition": comp, "stage": stage, "kickoff_utc": T0 + timedelta(days=days),
            "home": home, "away": away, "status": status, "home_goals": hg, "away_goals": ag}


MATCHES = [game("A", "B", 2, 0, 0), game("C", "D", 1, 1, 0), game("B", "C", 3, 1, 7), game("D", "A", 0, 0, 14),
           game("A", "C", None, None, 21, status="upcoming")]


def test_table_only_counts_games_before_the_kickoff():
    rows = {r["team"]: r for r in table_before(MATCHES, "Ligue 1", T0 + timedelta(days=7))}
    assert rows["A"] == {"team": "A", "position": 1, "played": 1, "points": 3}
    assert rows["B"]["played"] == 1 and rows["B"]["points"] == 0
    assert (rows["C"]["position"], rows["D"]["position"]) == (2, 3)  # level after a 1-1: by name
    assert len(rows) == 4


def test_ties_go_to_goal_difference_then_goals():
    rows = table_before(MATCHES, "Ligue 1", T0 + timedelta(days=30))
    assert [r["team"] for r in rows] == ["A", "B", "D", "C"]  # A 4, B 3 (+0, 3 goals), D 2, C 1


def test_european_table_skips_qualifiers():
    cup = [game("X", "Y", 1, 0, 0, comp="Champions League", stage="LEAGUE_STAGE"),
           game("X", "Z", 5, 0, -30, comp="Champions League", stage="QUALIFICATION")]
    rows = {r["team"]: r for r in table_before(cup, "Champions League", T0 + timedelta(days=1))}
    assert set(rows) == {"X", "Y"} and rows["X"]["points"] == 3


def test_deductions_are_points_the_results_dont_explain():
    published = {"Ligue 1": [{"team": "A", "position": 2, "played": 2, "points": 1},
                             {"team": "B", "position": 1, "played": 2, "points": 3}]}
    assert deductions(MATCHES, published, "Ligue 1", T0 + timedelta(days=30)) == {"A": -3}
