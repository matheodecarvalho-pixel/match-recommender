"""Watchability score for one match: each signal 0-1, weighted to 0-100.

Every signal returns (value, story) where story is the reason text, or None when the data
behind it is missing. Missing data scores 0 and never produces a reason.
"""
import math

from stats import LEAGUES, form

EUROPE = ("Champions League", "Europa League", "Conference League")
# football-data.org and ESPN stage names -> one name per knockout round.
ROUNDS = {
    "PLAYOFFS": "playoffs", "LAST_32": "playoffs", "LAST_16": "round_of_16", "QUARTER_FINALS": "quarter_finals",
    "SEMI_FINALS": "semi_finals", "FINAL": "final",
    "knockout-round-playoffs": "playoffs", "round-of-16": "round_of_16", "quarterfinals": "quarter_finals",
    "semifinals": "semi_finals", "final": "final",
}
KNOCKOUT_STAGES = set(ROUNDS)


def ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _row(table, team):
    return next((r for r in table or [] if r["team"] == team), None)


def signal_form(ctx, cfg):
    h, a = ctx["home_form"], ctx["away_form"]
    if not h or not a or min(h["games"], a["games"]) < cfg["min_matches"]:
        return 0.0, None
    both = h["ppg"] >= cfg["in_form_ppg"] and a["ppg"] >= cfg["in_form_ppg"]
    value = min(1.0, (h["ppg"] + a["ppg"]) / 2 / 3 + (cfg["both_in_form_bonus"] if both else 0))
    if both:
        story = ("both_in_form", {})
    elif value < cfg["min_value_for_reason"]:
        story = None  # poor form is not a reason to watch
    elif h["games"] == a["games"]:
        story = ("form", {"home": ctx["home"], "away": ctx["away"], "home_wins": h["wins"],
                          "away_wins": a["wins"], "n": h["games"]})
    else:
        story = None
    return value, story


def _season_factor(table, total_games, cfg):
    played = sum(r["played"] for r in table) / len(table)
    share = played / total_games if total_games else 0
    return max(cfg["min_factor"], min(1.0, share / cfg["full_weight_from_share"]))


def signal_stakes(ctx, cfg):
    comp, table = ctx["competition"], ctx["table"]
    if ctx["stage"] in KNOCKOUT_STAGES or ctx.get("knockout"):
        return cfg["knockout_match"], ("stakes_knockout", {})
    home, away = _row(table, ctx["home"]), _row(table, ctx["away"])
    if not home or not away:
        return 0.0, None

    def score(in_home, in_away):
        if in_home and in_away:
            return cfg["both_teams_in_race"]
        return cfg["one_team_in_race"] if in_home or in_away else 0.0

    ranked = [r["points"] for r in sorted(table, key=lambda r: r["position"])]
    pts = lambda place: ranked[place - 1] if 1 <= place <= len(ranked) else None

    races = []  # (value, story key, story values)
    if comp in EUROPE:
        gap = cfg["league_phase_points_gap"]
        for cut in cfg["league_phase_cutoffs"]:
            if pts(cut + 1) is not None:
                line = (pts(cut) + pts(cut + 1)) / 2
                near = lambda r: abs(r["points"] - line) <= gap
                races.append((score(near(home), near(away)), "stakes_cutoff", {"cutoff": cut}))
        total = 8  # league-phase games per team
    else:
        zones = cfg["league_zones"].get(comp)
        if not zones:
            return 0.0, None
        in_title = lambda r: pts(1) - r["points"] <= cfg["title_race_points_gap"]
        races.append((score(in_title(home), in_title(away)), "stakes_title",
                      {"gap": abs(home["points"] - away["points"])}))
        last_in, first_out = pts(zones["europe"]), pts(zones["europe"] + 1)
        if first_out is not None:
            in_europe = lambda r: (not in_title(r) and min(abs(r["points"] - last_in), abs(r["points"] - first_out))
                                   <= cfg["europe_race_points_gap"])
            races.append((score(in_europe(home), in_europe(away)), "stakes_europe", {}))
        safe = pts(len(ranked) - zones["relegation"])
        if safe is not None:
            in_releg = lambda r: r["points"] - safe <= cfg["relegation_points_gap"]
            races.append((score(in_releg(home), in_releg(away)), "stakes_relegation", {}))
        total = (len(ranked) - 1) * 2
    best = max(races, key=lambda r: r[0], default=(0.0, None, None))
    if best[0] <= 0:
        return 0.0, None
    value = best[0] * _season_factor(table, total, cfg)
    # "Title race" or "Relegation battle" only reads true when both teams are in it; with one
    # team in it the kind of race is still recorded (for My Feed) but never shown as a reason.
    quiet = best[0] < cfg["both_teams_in_race"]
    return value, (best[1], {**best[2], "_quiet": quiet})


def signal_entertainment(ctx, cfg):
    h, a = ctx["home_recent"], ctx["away_recent"]
    if not h or not a:
        return 0.0, None
    gpg = (h["goals_per_game"] + a["goals_per_game"]) / 2
    return min(1.0, gpg / cfg["goals_per_game_for_max"]), ("entertainment", {"goals_per_game": f"{gpg:.1f}"})


def signal_rivalry(ctx, cfg):
    r = ctx["rivalry"]
    best = (cfg[f"tier_{r['tier']}"], ("rivalry", {"rivalry_name": r["rivalry_name"]})) if r else (0.0, None)
    classic = cfg["european_classic"]
    n = ctx.get("european_meetings") or 0
    if n >= classic["min_meetings"] and classic["value"] > best[0]:
        best = (classic["value"], ("european_classic", {"n": n, "since": classic["since"][:4]}))
    return best


def signal_closeness(ctx, cfg):
    h, a = ctx["home_form"], ctx["away_form"]
    home, away = _row(ctx["table"], ctx["home"]), _row(ctx["table"], ctx["away"])
    parts, weights = 0.0, 0.0
    if home and away and len(ctx["table"]) > 1:
        gap = abs(home["position"] - away["position"]) / (len(ctx["table"]) - 1)
        parts += cfg["table_position_weight"] * (1 - gap)
        weights += cfg["table_position_weight"]
    if h and a:
        parts += cfg["form_gap_weight"] * (1 - abs(h["ppg"] - a["ppg"]) / 3)
        weights += cfg["form_gap_weight"]
    if not weights:
        return 0.0, None
    value = parts / weights
    story = None
    if home and away and value >= cfg["min_value_for_reason"]:
        story = ("closeness", {"home_pos": ordinal(home["position"]), "away_pos": ordinal(away["position"])})
    return value, story


def signal_records(ctx, cfg):
    best = None
    for chase in ctx.get("record_chases", []):
        d = chase["distance"]
        value = (cfg["within_1"] if d <= 1 else cfg["within_3"] if d <= 3
                 else cfg["within_5"] if d <= 5 else 0.0)
        if value and (best is None or value > best[0]):
            best = (value, ("records", chase["story"]))
    return best or (0.0, None)


def stature(team, clubs, cfg):
    """0-1 from the UEFA 5-year club coefficient: sqrt(points / points_for_full), capped at 1."""
    club = clubs.get(team)
    return min(1.0, math.sqrt(club["points"] / cfg["points_for_full"])) if club else 0.0


def signal_big_match(ctx, cfg):
    """Two big clubs: the product of both statures, so one giant against a minnow stays low."""
    clubs = ctx.get("stature") or {}
    value = stature(ctx["home"], clubs, cfg) * stature(ctx["away"], clubs, cfg)
    if value < cfg["min_value_for_reason"]:
        return value, None
    return value, ("big_match", {"home": ctx["home"], "away": ctx["away"],
                                 "home_rank": clubs[ctx["home"]]["rank"], "away_rank": clubs[ctx["away"]]["rank"]})


def expected_places(table, clubs):
    """Where each club 'should' be: the league's clubs ordered by UEFA coefficient, then the rest."""
    order = sorted(table, key=lambda r: -(clubs.get(r["team"], {}).get("points", 0)))
    return {r["team"]: i + 1 for i, r in enumerate(order)}


# How each league reads in a sentence ("in the Premier League", "in La Liga").
IN_LEAGUE = {"Premier League": "the Premier League", "La Liga": "La Liga", "Serie A": "Serie A",
             "Bundesliga": "the Bundesliga", "Ligue 1": "Ligue 1", "Eredivisie": "the Eredivisie",
             "Primeira Liga": "the Primeira Liga"}


def signal_giant_trouble(ctx, cfg):
    """A big club sitting well below where its stature puts it in its own league table."""
    clubs = ctx.get("stature") or {}
    best = (0.0, None)
    for team in (ctx["home"], ctx["away"]):
        league = (ctx.get("domestic") or {}).get(team)
        if not league or stature(team, clubs, ctx["big_match_cfg"]) < cfg["min_stature"]:
            continue
        name, table = league
        row = _row(table, team)
        if not row or row["played"] < cfg["min_games"]:
            continue
        expected = expected_places(table, clubs)[team]
        clamp = lambda x, lo, hi: max(0.0, min(1.0, (x - lo) / (hi - lo)))
        slip = clamp(row["position"] - expected, cfg["slip_start"], cfg["slip_full"])
        # Title favourites can be in trouble while still near the top: count the gap to the leader.
        leader = max(r["points"] for r in table)
        gap = leader - row["points"]
        behind = clamp(gap, cfg["gap_start"], cfg["gap_full"]) if expected <= cfg["title_contender_places"] else 0.0
        if slip >= behind and slip > best[0]:
            best = (slip, ("giant_trouble", {"team": team, "pos": ordinal(row["position"]), "league": IN_LEAGUE.get(name, name)}))
        elif behind > slip and behind > best[0]:
            best = (behind, ("giant_gap", {"team": team, "gap": gap, "league": IN_LEAGUE.get(name, name)}))
    return best


def signal_revenge(ctx, cfg):
    """Player/manager facing a former club, or a club facing the side that beat it.

    Club flags come first, so on a tie the club story wins.
    """
    options = [(f["value"], f["story"]) for f in ctx.get("club_revenge", [])]
    options += [(cfg[f["role"]], ("revenge", {"person": f["person"]})) for f in ctx.get("revenge", [])]
    if not options:
        return 0.0, None
    return max(options, key=lambda o: o[0])


SIGNALS = {"form": signal_form, "stakes": signal_stakes, "entertainment": signal_entertainment,
           "rivalry": signal_rivalry, "closeness": signal_closeness, "records": signal_records,
           "revenge": signal_revenge, "big_match": signal_big_match, "giant_trouble": signal_giant_trouble}


def score_match(ctx, config):
    breakdown, reasons = {}, []
    ctx = {**ctx, "big_match_cfg": config["signals"]["big_match"]}
    for name, fn in SIGNALS.items():
        if not config["weights"].get(name):
            continue  # switched off in scoring.json (records, for now)
        value, story = fn(ctx, config["signals"][name])
        points = config["weights"][name] * value
        breakdown[name] = {"value": round(value, 3), "points": round(points, 1)}
        if story:
            key, values = story
            breakdown[name]["kind"] = key
            if values.get("_quiet"):
                continue
            text = config["story"]["templates"][key].format(**values)
            breakdown[name]["reason"] = text
            if points > 0:
                reasons.append((points, text))

    base = sum(b["points"] for b in breakdown.values())
    bonus = config["competition_bonus"].get(ctx["competition"], 0)
    stage = config["knockout_bonus"].get(ROUNDS.get(ctx.get("stage") or ""), 0)
    favourites = set(config["favourites"]["teams"])
    favourite = ctx["home"] in favourites or ctx["away"] in favourites
    boost = config["favourites"]["boost"] if favourite else 0
    # Rescale: `reference` raw points (what a top real-world fixture collects) map to 100.
    total = min(100, round(100 * (base + bonus + stage) / config["scale"]["reference"]) + boost)

    must = config["must_watch"]
    tier1 = bool(ctx["rivalry"]) and ctx["rivalry"]["tier"] == 1 and must["tier_1_rivalry_always"]
    reasons.sort(key=lambda r: -r[0])
    story = config["story"]["separator"].join(t for _, t in reasons[:config["story"]["max_reasons"]])
    return {"score": total, "base": round(base, 1), "competition_bonus": bonus, "stage_bonus": stage,
            "favourite_boost": boost, "favourite": favourite,
            "must_watch": total >= must["score_threshold"] or tier1,
            "recommended": total >= must["recommended_threshold"],
            "story": story, "breakdown": breakdown}


def context(match, results, tables, rivalries, config, extras=None):
    """Everything the signals need for one match."""
    cfg = config["signals"]
    home, away, before = results.get(match["home"], []), results.get(match["away"], []), match["kickoff_utc"]
    n, n_goals = cfg["form"]["last_n_matches"], cfg["entertainment"]["last_n_matches"]
    ctx = {**match, "home_form": form(home, before, n), "away_form": form(away, before, n),
           "home_recent": form(home, before, n_goals), "away_recent": form(away, before, n_goals),
           "table": tables.get(match["competition"]),
           "domestic": {t: (name, tables[name]) for name in LEAGUES if name in tables
                        for t in (match["home"], match["away"]) if _row(tables[name], t)},
           "rivalry": rivalries.get(frozenset((match["home"], match["away"])))}
    ctx.update(extras or {})
    return ctx
