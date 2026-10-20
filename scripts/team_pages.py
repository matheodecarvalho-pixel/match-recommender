"""One JSON file per team for the My team tab: season story, table, form, results, fixtures,
head-to-head with the next opponent, points against last season and player lists.

Everything comes from data the pipeline already has (football-data.org, ESPN, our own scores);
a part with no data is left out, never filled in.

  python scripts/team_pages.py _site/teams     # after build.py and calendars.py
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path

from build import STYLES, in_table, load_inputs
from calendars import slug
from fd_client import COMPETITIONS, ROOT
from score import IN_LEAGUE, usual_place
from stats import CRESTS, LEAGUES, PARIS, streaks

OUTPUT = ROOT / "output"
EUROPE = ("Champions League", "Europa League", "Conference League")
FD_CODES = {name: code for code, name in COMPETITIONS.items()}
ESPN_EUROPE = {"Europa League": "uefa.europa", "Conference League": "uefa.europa.conf"}
FORM_GAMES = 10
PLAYER_ROWS = 5
MIN_APPS = {"rate": 3, "now": 5, "before": 10}  # appearances needed for per-game lists


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def side_of(m, team):
    """(goals for, goals against, home?) for a finished match, from the team's side."""
    home = m["home"] == team
    return (m["home_goals"], m["away_goals"], True) if home else (m["away_goals"], m["home_goals"], False)


def result(gf, ga):
    return "W" if gf > ga else "D" if gf == ga else "L"


# ---------- last season ----------

def last_season(registry):
    """Last season's finished matches: leagues and Champions League (football-data.org history files)
    plus the Europa and Conference League (ESPN monthly history)."""
    out = []
    for path in sorted((OUTPUT / "history").glob("fd_*_*.json")):
        code = path.stem.split("_")[1]
        name = COMPETITIONS.get(code)
        if not name:
            continue
        for m in json.loads(path.read_text(encoding="utf-8"))["matches"]:
            full = m["score"]["fullTime"]
            if m["status"] != "FINISHED" or full.get("home") is None:
                continue
            out.append({"competition": name, "stage": m.get("stage"), "kickoff": m["utcDate"],
                        "home": registry.from_fd(m["homeTeam"]), "away": registry.from_fd(m["awayTeam"]),
                        "home_goals": full["home"], "away_goals": full["away"]})
    this_start = season_start()
    for name, folder in ESPN_EUROPE.items():
        for path in sorted((OUTPUT / "europe_history" / folder).glob("*.json")):
            for m in json.loads(path.read_text(encoding="utf-8"))["matches"]:
                if m["status"] != "finished" or m["kickoff_utc"] >= this_start:
                    continue
                out.append({"competition": name, "stage": m.get("stage"), "kickoff": m["kickoff_utc"],
                            "home": registry.from_espn(m["home_espn_id"], m["home"]),
                            "away": registry.from_espn(m["away_espn_id"], m["away"]),
                            "home_goals": m["home_goals"], "away_goals": m["away_goals"]})
    return sorted(out, key=lambda m: m["kickoff"])


def season_start():
    today = datetime.now(timezone.utc)
    year = today.year if today.month >= 7 else today.year - 1
    return f"{year}-07-01"


def league_phase(m):
    """A league or league-phase game (where points are counted), not a knockout tie."""
    return m["competition"] not in EUROPE or m.get("stage") in (None, "LEAGUE_STAGE", "league-phase")


def points_after(games, team, n):
    pts = 0
    for m in games[:n]:
        gf, ga, _ = side_of(m, team)
        pts += 3 if gf > ga else 1 if gf == ga else 0
    return pts


def versus_last_season(team, now_games, before):
    """Points after the same number of games as last season, per competition this season.

    Europe is compared with last season's European league phase, whichever cup it was in."""
    rows = []
    for comp in sorted({m["competition"] for m in now_games}, key=lambda c: (c in EUROPE, c)):
        mine = [m for m in now_games if m["competition"] == comp and league_phase(m)]
        n = len(mine)
        if not n:
            continue
        row = {"competition": comp, "games": n, "points": points_after(mine, team, n)}
        pool = [m for m in before if team in (m["home"], m["away"]) and league_phase(m)]
        if comp in EUROPE:
            cups = [c for c in EUROPE if any(m["competition"] == c for m in pool)]
            past = [m for m in pool if m["competition"] in cups[:1]]
            row["last_competition"] = cups[0] if cups else None
        else:
            past = [m for m in pool if m["competition"] == comp]
            row["last_competition"] = comp if past else None
        if len(past) >= n:
            row["last_points"] = points_after(past, team, n)
            row["diff"] = row["points"] - row["last_points"]
        rows.append(row)
    return rows


# ---------- players ----------

def players(team):
    """This season's and last season's league stats for the club's squad (ESPN rosters)."""
    now, before, past_all = None, None, {}
    years = sorted({json.loads(p.read_text(encoding="utf-8"))["season"] for p in (OUTPUT / "players").glob("*.json")}) \
        if (OUTPUT / "players").exists() else []
    if not years:
        return None
    this_year = years[-1]
    for path in (OUTPUT / "players").glob("*.json"):
        d = json.loads(path.read_text(encoding="utf-8"))
        if d["season"] == this_year and d["team"] == team:
            now = d
        elif d["season"] < this_year:
            for p in d["players"]:  # last season at any club we follow, matched by ESPN player id
                old = past_all.get(p["id"])
                if not old or p["stats"].get("appearances", 0) > old["stats"].get("appearances", 0):
                    past_all[p["id"]] = {**p, "team": d["team"]}
    if not now or not now["players"]:
        return None
    squad = now["players"]
    s = lambda p, k: p["stats"].get(k, 0) or 0
    apps = lambda p: s(p, "appearances")
    def row(p, value, extra=None):
        return {"name": p["name"], "position": p.get("position"), "value": value, "apps": int(apps(p)), **(extra or {})}
    def top(key, label_fn, keep=lambda p: True):
        ranked = sorted((p for p in squad if keep(p) and key(p) > 0), key=lambda p: (-key(p), apps(p)))
        return [row(p, label_fn(p)) for p in ranked[:PLAYER_ROWS]]

    out = {"league": now["league"],
           "scorers": top(lambda p: s(p, "totalGoals"), lambda p: int(s(p, "totalGoals"))),
           "assists": top(lambda p: s(p, "goalAssists"), lambda p: int(s(p, "goalAssists"))),
           "shots_on_target": top(lambda p: s(p, "shotsOnTarget") / apps(p), lambda p: round(s(p, "shotsOnTarget") / apps(p), 1),
                                  keep=lambda p: apps(p) >= MIN_APPS["rate"]),
           "most_used": top(lambda p: apps(p) - s(p, "subIns"), lambda p: int(apps(p) - s(p, "subIns")))}
    # Goal involvements (goals + assists) per appearance against last season's.
    changes = []
    for p in squad:
        old = past_all.get(p["id"])
        if not old or apps(p) < MIN_APPS["now"] or apps(old) < MIN_APPS["before"]:
            continue
        rate = (s(p, "totalGoals") + s(p, "goalAssists")) / apps(p)
        was = (s(old, "totalGoals") + s(old, "goalAssists")) / apps(old)
        changes.append((rate - was, p, rate, was, old["team"]))
    up = sorted((c for c in changes if c[0] > 0), key=lambda c: -c[0])[:3]
    down = sorted((c for c in changes if c[0] < 0), key=lambda c: c[0])[:3]
    fmt = lambda c: row(c[1], round(c[2], 2), {"was": round(c[3], 2), "change": round(c[0], 2),
                                              "last_club": c[4] if c[4] != team else None})
    out["up"], out["down"] = [fmt(c) for c in up], [fmt(c) for c in down]
    return out


# ---------- the page ----------

def team_page(team, inp, ranked, archive, before, h2h, h2h_espn):
    matches = sorted((m for m in inp["matches"] if team in (m["home"], m["away"])), key=lambda m: m["kickoff_utc"])
    played = [m for m in matches if m["status"] == "finished" and m["home_goals"] is not None]
    upcoming = [m for m in matches if m["status"] == "upcoming"]
    league = next((c for c in LEAGUES if any(m["competition"] == c for m in matches)), None)
    table = inp["tables"].get(league) if league else None
    row = next((r for r in table or [] if r["team"] == team), None)

    page = {"team": team, "crest": CRESTS.get(team), "style": STYLES.get(team), "league": league,
            "competitions": sorted({m["competition"] for m in matches}, key=lambda c: (c in EUROPE, c)),
            "generated_at": datetime.now(PARIS).isoformat()}

    # League position and the teams around it.
    if row:
        i = table.index(row)
        page["table"] = {"position": row["position"], "points": row["points"], "played": row["played"],
                         "size": len(table),
                         "rows": [{"team": r["team"], "position": r["position"], "points": r["points"], "played": r["played"]}
                                  for r in table[max(0, i - 2): i + 3]],
                         "leader": {"team": table[0]["team"], "points": table[0]["points"]}}

    # Form and season numbers, all competitions.
    page["form"] = [[result(*side_of(m, team)[:2]), f"{side_of(m, team)[0]}-{side_of(m, team)[1]}",
                     m["away"] if m["home"] == team else m["home"]] for m in played[-FORM_GAMES:]]
    if played:
        rec = {"home": [0, 0, 0], "away": [0, 0, 0]}
        gf = ga = clean = 0
        best = worst = None
        for m in played:
            f, a, home = side_of(m, team)
            rec["home" if home else "away"]["WDL".index(result(f, a))] += 1
            gf, ga, clean = gf + f, ga + a, clean + (a == 0)
            margin = (f - a, f)
            line = {"opponent": m["away"] if home else m["home"], "score": f"{f}-{a}", "competition": m["competition"],
                    "date": m["kickoff_utc"].astimezone(PARIS).date().isoformat()}
            if f > a and (best is None or margin > best[0]):
                best = (margin, line)
            if f < a and (worst is None or (a - f, a) > worst[0]):
                worst = ((a - f, a), line)
        results = inp["results"].get(team, [])
        ours = [r for r in results if r["competition"] in COMPETITIONS.values() or r["competition"] in EUROPE]
        run = streaks(ours)
        page["numbers"] = {"games": len(played), "home": rec["home"], "away": rec["away"],
                           "scored_per_game": round(gf / len(played), 2), "conceded_per_game": round(ga / len(played), 2),
                           "clean_sheets": clean, "biggest_win": best[1] if best else None,
                           "worst_defeat": worst[1] if worst else None,
                           "win_run": run["win"], "unbeaten_run": run["unbeaten"]}

    # Recent results, newest first, with the score eyeball gave each game before kickoff.
    page["results"] = [{"id": m["id"], "date": m["kickoff_utc"].astimezone(PARIS).date().isoformat(),
                        "competition": m["competition"], "home": m["home"], "away": m["away"],
                        "home_goals": m["home_goals"], "away_goals": m["away_goals"],
                        "interest": (archive.get(m["id"]) or {}).get("score")} for m in reversed(played)]

    # Next matches.
    def fixture(m):
        r = ranked.get(m["id"])
        home = m["home"] == team
        opp = m["away"] if home else m["home"]
        opp_table = inp["tables"].get(m["competition"]) if in_table(m) else None
        opp_row = next((x for x in opp_table or [] if x["team"] == opp), None)
        rivalry = inp["rivalries"].get(frozenset((m["home"], m["away"])))
        revenge = inp["moves"].flags(m["home"], m["away"], m["kickoff_utc"])
        return {"id": m["id"], "kickoff_paris": m["kickoff_utc"].astimezone(PARIS).isoformat(),
                "time_confirmed": m.get("time_confirmed", True), "competition": m["competition"], "stage": m.get("stage"),
                "home": m["home"], "away": m["away"], "opponent": opp, "at_home": home,
                "opponent_position": opp_row["position"] if opp_row and opp_row["played"] else None,
                "rivalry": rivalry["rivalry_name"] if rivalry else None,
                "revenge": [f"{f['person']} ({f['team']}) faces his former club" for f in revenge],
                "score": r["score"] if r else None, "must_watch": r["must_watch"] if r else False,
                "recommended": r.get("recommended", False) if r else False,
                "story_sides": r.get("story_sides") if r else None, "positions": r.get("positions") if r else None,
                "forms": r.get("forms") if r else None, "espn": r.get("espn") if r else None}
    page["next"] = [fixture(m) for m in upcoming[:5]]

    # Head-to-head with the next opponent: football-data.org's last 10 meetings, else what we have.
    if upcoming:
        nxt = upcoming[0]
        opp = nxt["away"] if nxt["home"] == team else nxt["home"]
        meetings = []
        key = "-".join(str(i) for i in sorted(nxt["fd_ids"])) if nxt.get("fd_ids") else None
        if key and key in h2h:
            mine = nxt["fd_ids"][0 if nxt["home"] == team else 1]
            for x in h2h[key]["meetings"]:
                home = x["home_id"] == mine
                f, a = (x["home_goals"], x["away_goals"]) if home else (x["away_goals"], x["home_goals"])
                meetings.append({"date": x["date"], "competition": x["competition"], "at_home": home,
                                 "score": f"{f}-{a}", "result": result(f, a)})
        elif nxt["id"].startswith("espn-") and nxt["id"][5:] in h2h_espn:
            entry = h2h_espn[nxt["id"][5:]]
            mine = entry["home_espn_id"] if nxt["home"] == team else entry["away_espn_id"]
            for x in entry["meetings"]:
                home = x["home_espn_id"] == mine
                f, a = (x["home_goals"], x["away_goals"]) if home else (x["away_goals"], x["home_goals"])
                meetings.append({"date": x["date"], "competition": x["competition"], "at_home": home,
                                 "score": f"{f}-{a}", "result": result(f, a)})
        if not meetings:
            for m in before + [{**m, "kickoff": m["kickoff_utc"].isoformat()} for m in played]:
                if {m["home"], m["away"]} == {team, opp}:
                    f, a = (m["home_goals"], m["away_goals"]) if m["home"] == team else (m["away_goals"], m["home_goals"])
                    meetings.append({"date": m["kickoff"][:10], "competition": m["competition"], "at_home": m["home"] == team,
                                     "score": f"{f}-{a}", "result": result(f, a)})
        meetings.sort(key=lambda x: x["date"], reverse=True)
        if meetings:
            tally = {k: sum(1 for x in meetings if x["result"] == k) for k in "WDL"}
            page["head_to_head"] = {"opponent": opp, "meetings": meetings[:10], "wins": tally["W"],
                                    "draws": tally["D"], "losses": tally["L"]}

    page["vs_last_season"] = versus_last_season(team, played, before)
    page["story"] = story(team, page, league, row, table, inp)
    page["players"] = players(team)
    return page


def story(team, page, league, row, table, inp):
    """The season so far in a few plain sentences, each from data on this page."""
    lines = []
    if row and row["played"]:
        usual, seasons = usual_place(inp["history"], league, team)
        where = f"{ordinal(row['position'])} in {IN_LEAGUE.get(league, league)}"
        if seasons >= 3:
            diff = row["position"] - usual
            verdict = ("well above their usual level" if diff <= -4 else "above their usual level" if diff <= -2
                       else "well below their usual level" if diff >= 4 else "below their usual level" if diff >= 2
                       else "right where they usually finish")
            lines.append(f"{where}, usually {ordinal(round(usual))}: {verdict}.")
        else:
            lines.append(f"{where} after {plural(row['played'], 'game')}.")
        leader = table[0]
        if leader["team"] == team:
            second = table[1]["points"] if len(table) > 1 else row["points"]
            lines.append(f"Top of the table, {plural(row['points'] - second, 'point')} clear." if row["points"] > second
                         else "Top of the table on goal difference.")
        else:
            lines.append(f"{plural(leader['points'] - row['points'], 'point')} behind leaders {leader['team']}.")
    n = page.get("numbers")
    if n:
        if n["win_run"] >= 3:
            lines.append(f"{n['win_run']} wins in a row.")
        elif n["unbeaten_run"] >= 4:
            lines.append(f"Unbeaten in {n['unbeaten_run']}.")
        elif page["form"] and all(f[0] != "W" for f in page["form"][-4:]):
            lines.append("No win in the last 4.")
    for r in page["vs_last_season"]:
        if "diff" in r and r["competition"] not in EUROPE:
            word = "up" if r["diff"] > 0 else "down" if r["diff"] < 0 else "level"
            lines.append(f"{plural(abs(r['diff']), 'point')} {word} on last season after {r['games']} league games."
                         if r["diff"] else f"Same points as last season after {r['games']} league games.")
    return lines


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    inp = load_inputs(now)
    registry = inp["registry"]
    ranked_path = OUTPUT / "matches_ranked.json"
    ranked = {m["id"]: m for m in json.loads(ranked_path.read_text(encoding="utf-8"))["matches"]} if ranked_path.exists() else {}
    archive_path = OUTPUT / "score_archive.json"
    archive = json.loads(archive_path.read_text(encoding="utf-8")) if archive_path.exists() else {}
    h2h_path = OUTPUT / "h2h_next.json"
    h2h = json.loads(h2h_path.read_text(encoding="utf-8")) if h2h_path.exists() else {}
    espn_path = OUTPUT / "h2h_espn.json"
    h2h_espn = json.loads(espn_path.read_text(encoding="utf-8")) if espn_path.exists() else {}
    before = last_season(registry)
    teams = {t for m in inp["matches"] for t in (m["home"], m["away"])}
    for team in sorted(teams):
        page = team_page(team, inp, ranked, archive, before, h2h, h2h_espn)
        (out / f"{slug(team)}.json").write_text(json.dumps(page, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(teams)} team pages written to {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else OUTPUT / "teams")
