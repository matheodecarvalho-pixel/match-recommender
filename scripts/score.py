"""Watchability score for one match: each signal 0-1, weighted to 0-100.

Every signal returns (value, story) where story is the reason text, or None when the data
behind it is missing. Missing data scores 0 and never produces a reason.
"""
from stats import form

EUROPE = ("Champions League", "Europa League", "Conference League")
KNOCKOUT_STAGES = {"PLAYOFFS", "LAST_32", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS", "FINAL"}


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
    return value, (best[1], best[2])


def signal_entertainment(ctx, cfg):
    h, a = ctx["home_recent"], ctx["away_recent"]
    if not h or not a:
        return 0.0, None
    gpg = (h["goals_per_game"] + a["goals_per_game"]) / 2
    return min(1.0, gpg / cfg["goals_per_game_for_max"]), ("entertainment", {"goals_per_game": f"{gpg:.1f}"})


def signal_rivalry(ctx, cfg):
    r = ctx["rivalry"]
    if not r:
        return 0.0, None
    return cfg[f"tier_{r['tier']}"], ("rivalry", {"rivalry_name": r["rivalry_name"]})


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


def signal_revenge(ctx, cfg):
    flags = ctx.get("revenge", [])
    if not flags:
        return 0.0, None
    top = max(flags, key=lambda f: cfg[f["role"]])
    return cfg[top["role"]], ("revenge", {"person": top["person"]})


SIGNALS = {"form": signal_form, "stakes": signal_stakes, "entertainment": signal_entertainment,
           "rivalry": signal_rivalry, "closeness": signal_closeness, "records": signal_records,
           "revenge": signal_revenge}


def score_match(ctx, config):
    breakdown, reasons = {}, []
    for name, fn in SIGNALS.items():
        value, story = fn(ctx, config["signals"][name])
        points = config["weights"][name] * value
        breakdown[name] = {"value": round(value, 3), "points": round(points, 1)}
        if story:
            key, values = story
            text = config["story"]["templates"][key].format(**values)
            breakdown[name]["reason"] = text
            if points > 0:
                reasons.append((points, text))

    base = sum(b["points"] for b in breakdown.values())
    bonus = config["competition_bonus"].get(ctx["competition"], 0)
    favourites = set(config["favourites"]["teams"])
    favourite = ctx["home"] in favourites or ctx["away"] in favourites
    boost = config["favourites"]["boost"] if favourite else 0
    total = min(100, round(base + bonus + boost))

    must = config["must_watch"]
    tier1 = bool(ctx["rivalry"]) and ctx["rivalry"]["tier"] == 1 and must["tier_1_rivalry_always"]
    reasons.sort(key=lambda r: -r[0])
    story = config["story"]["separator"].join(t for _, t in reasons[:config["story"]["max_reasons"]])
    return {"score": total, "base": round(base, 1), "competition_bonus": bonus, "favourite_boost": boost,
            "favourite": favourite, "must_watch": total >= must["score_threshold"] or tier1,
            "story": story, "breakdown": breakdown}


def context(match, results, tables, rivalries, config, extras=None):
    """Everything the signals need for one match."""
    cfg = config["signals"]
    home, away, before = results.get(match["home"], []), results.get(match["away"], []), match["kickoff_utc"]
    n, n_goals = cfg["form"]["last_n_matches"], cfg["entertainment"]["last_n_matches"]
    ctx = {**match, "home_form": form(home, before, n), "away_form": form(away, before, n),
           "home_recent": form(home, before, n_goals), "away_recent": form(away, before, n_goals),
           "table": tables.get(match["competition"]),
           "rivalry": rivalries.get(frozenset((match["home"], match["away"])))}
    ctx.update(extras or {})
    return ctx
