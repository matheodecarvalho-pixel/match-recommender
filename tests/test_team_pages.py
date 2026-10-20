from team_pages import points_after, versus_last_season


def game(comp, home, away, hg, ag, stage=None, kickoff="2026-09-01"):
    return {"competition": comp, "stage": stage, "home": home, "away": away, "home_goals": hg, "away_goals": ag,
            "kickoff": kickoff}


def test_points_after_counts_only_the_first_games():
    games = [game("Serie A", "Milan", "X", 2, 0), game("Serie A", "Y", "Milan", 1, 1), game("Serie A", "Milan", "Z", 0, 1)]
    assert points_after(games, "Milan", 2) == 4
    assert points_after(games, "Milan", 3) == 4


def test_league_compares_with_same_league_and_europe_with_last_cup():
    now = [game("Serie A", "Milan", "X", 1, 0), game("Serie A", "Milan", "Y", 1, 0),
           game("Europa League", "Milan", "Q", 0, 0, stage="league-phase")]
    before = [game("Serie A", "Milan", "A", 0, 1), game("Serie A", "B", "Milan", 0, 0), game("Serie A", "Milan", "C", 3, 0),
              game("Champions League", "Milan", "D", 2, 1, stage="LEAGUE_STAGE"),
              game("Champions League", "Milan", "E", 5, 0, stage="QUARTER_FINALS")]
    rows = {r["competition"]: r for r in versus_last_season("Milan", now, before)}
    assert rows["Serie A"] == {"competition": "Serie A", "games": 2, "points": 6, "last_competition": "Serie A",
                               "last_points": 1, "diff": 5}
    assert rows["Europa League"]["last_competition"] == "Champions League"
    assert rows["Europa League"]["diff"] == 1 - 3


def test_no_last_season_means_no_comparison():
    rows = versus_last_season("Como", [game("Serie A", "Como", "X", 1, 1)], [])
    assert rows[0]["last_competition"] is None and "diff" not in rows[0]
