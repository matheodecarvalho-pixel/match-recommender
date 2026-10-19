"""Draft play-style profiles: journalism consensus where found, season stats otherwise.

Reads data/style_stats.json (fetch_style_stats.py) and the researched picks below; writes
data/play_styles.json. Each club gets a profile, a confidence and its evidence:
  high    a 2026-27 source and the stats agree
  medium  a 2026-27 source, or the coach's well-documented approach, not yet clear in the stats
  low     season stats only (rules below), or a long-standing club identity not checked for 2026-27

  python scripts/classify_styles.py
"""
import json
from datetime import date

from fd_client import ROOT

PROFILES = {
    "possession": "🎯 Possession & control",
    "press": "⚡ High press & transition",
    "low_block": "🧱 Low block & counter",
    "direct": "💪 Direct & physical",
    "chaos": "🎢 All-out attack",
    "pragmatic": "♟️ Pragmatic / balanced",
}

S = {  # sources used below
    "pl_trends": "https://www.martincid.com/sports-en/premier-league-2026-27-tactical-trends-ranked/",
    "pl_espn": "https://www.espn.com/soccer/story/_/id/49644584/premier-league-2026-2027-preview-offseason-moves-stats-analysis-predictions-teams",
    "pl_new": "https://www.goal.com/en-us/news/a-new-wave-of-managers-could-make-the-2026-27-premier-league-title-race-highly-unpredictable/blt20455e0aa4f86c34",
    "pl_new2": "https://www.boxofficeevents.com/football-news/every-new-premier-league-manager-in-202627-styles-what-to-expect-and-will-they-survive-part-1",
    "liga_prev": "https://extratimetalk.com/la-liga-2026-27-preview-spanish-top-flight/",
    "barca": "https://tacticalfootballanalysis.com/barcelona-athletic-club-la-liga-2026-2027-tactical-analysis-tactics/",
    "villarreal": "https://cuatropicas.com/2026/08/10/analisis-villarreal-26-27/",
    "sa_aj": "https://www.aljazeera.com/sports/2026/8/21/serie-a-key-talking-points-heading-into-the-new-2026-27-season",
    "sa_alm": "https://directoroffootball.com/2026-27-serie-a-almanac/",
    "sa_mod": "https://calciodangolo.com/allenatori-serie-a-2026-2027-moduli-squadra-per-squadra/",
    "milan": "https://www.socios.com/ac-milan-2026-27-season-squad-serie-a-european-path/",
    "bl_leipzig": "https://sports.yahoo.com/articles/bundesliga-2026-27-tactical-previews-120500718.html",
    "bl_bayern": "https://www.getfootballnewsgermany.com/2026/bundesliga-bayern-preview-26/",
    "bl_bvb": "https://www.getfootballnewsgermany.com/2026/bundesliga-dortmund-prev-26/",
    "bl_freiburg": "https://www.getfootballnewsgermany.com/2026/bundesliga-freiburg-preview-26/",
    "bl_more": "https://ca.sports.yahoo.com/news/bundesliga-2026-27-tactical-previews-185500946.html",
    "l1_coaches": "https://www.sportsillustrated.fr/football/ligue-1-2026-2027-ce-qui-change-cette-saison/",
    "ere_ajax": "https://www.goal.com/en/news/too-ambitious-or-realistic-this-is-how-michel-and-cruyff-want-to-make-ajax-title-contenders-again/bltc9c073cfbf1081a8",
    "ere_psv": "https://www.whoscored.com/matches/1982266/preview/netherlands-eredivisie-2026-2027-ajax-psv-eindhoven",
    "pt_coaches": "https://www.flashscore.pt/noticias/futebol-liga-portugal-betclic-os-18-treinadores-do-campeonato/EBS9I3wC/",
}

# Researched picks: club -> (profile, confidence, coach, why, source key)
PICKS = {
    # Premier League
    "Manchester City": ("possession", "high", "Enzo Maresca", "Back-three build-up, patient circulation; 63% possession", "pl_trends"),
    "Brighton & Hove Albion": ("possession", "high", "Fabian Hürzeler", "4-2-2-2 press, but dominates the ball: 62% possession, 20 shots a game", "pl_trends"),
    "Arsenal": ("possession", "medium", "Mikel Arteta", "Controlled possession and the league's set-piece reference; 61% possession, 0.6 goals conceded", "pl_trends"),
    "Tottenham Hotspur": ("possession", "medium", "Roberto De Zerbi", "Builds from the back to bait the press, then hard pressing; results not there yet", "pl_new"),
    "Liverpool": ("press", "medium", "Arne Slot", "Positional press with 3–4 pressers, quick attacks after regains", "pl_trends"),
    "Newcastle United": ("press", "medium", None, "Trademark aggression and energy, attacks every game", "pl_espn"),
    "AFC Bournemouth": ("press", "high", "Marco Rose", "High-intensity 4-4-2, concedes under 10 shots a game", "pl_new2"),
    "Crystal Palace": ("press", "medium", "Pierre Sage", "High-intensity back three, like his Lens side", "pl_new2"),
    "Chelsea": ("pragmatic", "medium", "Xabi Alonso", "Changes shape depending on the opponent", "pl_new"),
    "Aston Villa": ("pragmatic", "high", "Unai Emery", "Plans for each opponent, alters formations, strong game management", "pl_new"),
    "Brentford": ("direct", "high", None, "Set pieces and directness: more long throws into the box than anyone", "pl_trends"),
    "Manchester United": ("press", "medium", None, "3-4-3 that has bedded in, 18.7 shots a game", "pl_trends"),
    # La Liga
    "Barcelona": ("possession", "high", "Hansi Flick", "Fluid build-up, rotations, aggressive press; 70% possession, 4.4 goals a game", "barca"),
    "Real Madrid": ("low_block", "medium", "José Mourinho", "Compact deep block against big sides, ruthless in transition", "liga_prev"),
    "Villarreal": ("possession", "medium", "Iñigo Pérez", "More presence up front; 58% possession", "villarreal"),
    "Athletic Club": ("press", "medium", None, "4-2-3-1 that presses in a 4-4-2", "barca"),
    "Getafe": ("direct", "medium", None, "Long-standing physical, duel-heavy identity; 39% possession, 14 fouls a game", None),
    # Serie A
    "Inter": ("possession", "medium", "Cristian Chivu", "3-5-2 built around midfield control; 62% possession, 22.6 shots", "sa_aj"),
    "Como": ("possession", "high", "Cesc Fàbregas", "Attacking 4-2-3-1 on the ball; 59% possession", "sa_aj"),
    "AC Milan": ("possession", "high", "Rúben Amorim", "Wants controlling possession and many players in the box", "milan"),
    "Juventus": ("possession", "medium", "Luciano Spalletti", "Ball-dominant; 57% possession and only 8 shots conceded a game", "sa_aj"),
    "Roma": ("press", "medium", "Gian Piero Gasperini", "Man-to-man pressing all over the pitch; 0.9 goals conceded", "sa_alm"),
    "Napoli": ("pragmatic", "medium", "Massimiliano Allegri", "Allegri's pragmatism: control the game, not the ball", "sa_alm"),
    "Atalanta": ("possession", "medium", "Maurizio Sarri", "Sarri's possession 4-3-3 replacing a high-press side; not visible in the stats yet", "sa_mod"),
    "Lazio": ("pragmatic", "medium", "Gennaro Gattuso", "4-3-3 / 4-2-3-1, solid: 0.6 goals conceded a game", "sa_mod"),
    "Bologna": ("pragmatic", "low", "Domenico Tedesco", "4-2-3-1, first Serie A season for the coach", "sa_mod"),
    "Fiorentina": ("pragmatic", "low", "Fabio Grosso", "4-3-3, many shots but 2.4 conceded a game", "sa_mod"),
    "Genoa": ("pragmatic", "low", "Daniele De Rossi", "3-4-2-1 / 3-4-1-2", "sa_mod"),
    "Torino": ("pragmatic", "low", "Ignazio Abate", "3-5-2 / 3-4-2-1, new coach", "sa_mod"),
    "Frosinone": ("chaos", "medium", "Massimiliano Alvini", "Organised and on the front foot, 17 shots for and 20 against a game", "sa_aj"),
    # Bundesliga
    "Bayern Munich": ("possession", "high", "Vincent Kompany", "Dominant on the ball and pushes four attackers onto the last line; 68% possession", "bl_bayern"),
    "RB Leipzig": ("press", "high", "Martín Demichelis", "Intense pressing and quick vertical attacks after turnovers", "bl_leipzig"),
    "Borussia Dortmund": ("press", "high", "Niko Kovač", "3-4-2-1 high press with a high line that invites counters", "bl_bvb"),
    "Eintracht Frankfurt": ("press", "high", "Adi Hütter", "Intensity, aggressive pressing, ball forward fast; 4-2-2-2", "bl_more"),
    "Hoffenheim": ("press", "medium", "Christian Ilzer", "4-2-2-2 built on pressing and running", "bl_more"),
    "Mainz": ("press", "high", "Urs Fischer", "Aggressive ball recoveries turned into immediate vertical attacks", "bl_more"),
    "SC Freiburg": ("pragmatic", "medium", None, "Defends in a 4-4-2, efficient: 2.6 goals for, 9 shots against", "bl_freiburg"),
    "Union Berlin": ("low_block", "low", None, "Long-standing compact, deep identity; 44% possession", None),
    # Ligue 1
    "Paris Saint-Germain": ("possession", "high", "Luis Enrique", "Total control: 66% possession, 22 shots a game", None),
    "Paris FC": ("possession", "medium", "Liam Rosenior", "Possession-based build-up, his style at Strasbourg; concedes under 10 shots", "l1_coaches"),
    "Lyon": ("pragmatic", "medium", "Paulo Fonseca", "Proactive coach, but balanced so far: 50% possession, 0.9 conceded", "l1_coaches"),
    "Monaco": ("pragmatic", "low", "Filipe Luís", "His Flamengo dominated the ball; not visible yet (49% possession)", "l1_coaches"),
    "Lille": ("pragmatic", "low", "Davide Ancelotti", "New coach; 49% possession, solid defensively", "l1_coaches"),
    # Eredivisie
    "PSV": ("press", "medium", "Peter Bosz", "Bosz's high-tempo 4-3-3 with an aggressive press; 60% possession", "ere_psv"),
    "Ajax": ("possession", "medium", "Míchel", "Positional 4-3-3 built on the ball; 62% possession, 22 shots", "ere_ajax"),
    # Primeira Liga
    "Benfica": ("possession", "medium", "Marco Silva", "Ball-dominant: 60% possession, 9 shots conceded", "pt_coaches"),
    "Porto": ("pragmatic", "medium", "Francesco Farioli", "Controlled, efficient: 0.9 goals conceded a game", "pt_coaches"),
    "Sporting CP": ("pragmatic", "low", "Rui Borges", "Balanced, 55% possession", "pt_coaches"),
}

# Long-standing club identities for European clubs outside our leagues (not checked for 2026-27).
IDENTITIES = {
    "RB Salzburg": ("press", "Red Bull school: gegenpress and vertical attacks"),
    "FC Midtjylland": ("direct", "Set-piece specialists, physical and data-driven"),
    "Slavia Prague": ("direct", "Intense, physical, aerial and set-piece threat"),
    "Union St.-Gilloise": ("direct", "Direct, set pieces and transitions"),
    "Bodo/Glimt": ("possession", "Possession and press at home, their trademark"),
    "Celtic": ("possession", "Dominates the ball domestically"),
    "SK Sturm Graz": ("press", "High-press, high-intensity Austrian school"),
    "Olympiacos": ("direct", "Mendilibar-style direct, intense football"),
}


def from_stats(s):
    """Season-stats rules for clubs without a researched pick."""
    p, sh, sha = s["possession"], s["shots"], s["shots_against"]
    open_game = s["goals"] + s["goals_against"]
    if p >= 58:
        return "possession", f"{p:.0f}% possession"
    if p <= 42 and sha >= 15:
        return "low_block", f"{p:.0f}% possession, {sha:.0f} shots conceded a game"
    if s["fouls"] >= 14 and p <= 50:
        return "direct", f"{s['fouls']:.0f} fouls a game, {p:.0f}% possession"
    if open_game >= 3.6 or (sh >= 15 and sha >= 15):
        return "chaos", f"{open_game:.1f} goals a game (both ends), {sh:.0f} shots for / {sha:.0f} against"
    if sh >= 16 and p >= 48:
        return "press", f"{sh:.0f} shots a game at {p:.0f}% possession"
    return "pragmatic", f"{p:.0f}% possession, {sh:.0f} shots for / {sha:.0f} against"


LEAGUE = {"eng.1": "Premier League", "esp.1": "La Liga", "ita.1": "Serie A", "ger.1": "Bundesliga",
          "fra.1": "Ligue 1", "ned.1": "Eredivisie", "por.1": "Primeira Liga"}


def main():
    stats = json.loads((ROOT / "data" / "style_stats.json").read_text(encoding="utf-8"))["teams"]
    clubs = {}
    for team, s in stats.items():
        league = LEAGUE.get(s.get("league"))
        numbers = {k: s[k] for k in ("games", "possession", "shots", "shots_against", "goals", "goals_against", "fouls")}
        if team in PICKS:
            profile, conf, coach, why, src = PICKS[team]
            data_profile, _ = from_stats(s)
            if conf == "medium" and data_profile == profile and src:
                conf = "high"  # the source and the stats agree
            clubs[team] = {"league": league, "profile": profile, "confidence": conf, "coach": coach,
                           "why": why, "source": S.get(src), "basis": "research" if src else "club identity + stats",
                           "stats": numbers}
        elif league:
            profile, why = from_stats(s)
            clubs[team] = {"league": league, "profile": profile, "confidence": "low", "coach": None,
                           "why": why, "source": None, "basis": "stats", "stats": numbers}
        elif team in IDENTITIES:
            profile, why = IDENTITIES[team]
            clubs[team] = {"league": "Europe", "profile": profile, "confidence": "low", "coach": None,
                           "why": why, "source": None, "basis": "club identity (not checked for 2026-27)",
                           "stats": numbers}
    unclassified = sorted(t for t, s in stats.items() if t not in clubs)
    out = {"generated": date.today().isoformat(), "status": "draft for review", "profiles": PROFILES,
           "clubs": clubs, "unclassified": unclassified}
    (ROOT / "data" / "play_styles.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    from collections import Counter
    print(len(clubs), "clubs classified;", len(unclassified), "European clubs left for later")
    print(Counter(c["profile"] for c in clubs.values()))
    print(Counter(c["confidence"] for c in clubs.values()))


if __name__ == "__main__":
    main()
