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
    "pl_list": "https://thesportscast.net/2026/08/06/premier-league-managers-2026-27-full-list-of-every-head-coach-ahead-of-the-new-season/",
    "sa_list": "https://www.legaseriea.it/serie-a/news/gli-allenatori-della-serie-a-enilive-2026-27",
    "liga_list": "https://www.eldesmarque.com/futbol/liga-1a-division/20260618/banquillos-laliga-2026-2027-nuevos-entrenadores_18_019482771.html",
    "l1_list": "https://www.flashscore.fr/actualites/football-ligue-1-ligue-1-2026-2027-la-liste-complete-des-18-entraineurs-avec-un-record-de-changements/8Ie2nfWh/",
    "bl_kicker": "https://www.kicker.de/sc-freiburg/team-trainer",
    "ere_telstar": "https://www.footballtransfers.com/nl/transfernieuws/nl-eredivisie/2026/05/telstar-plukt-nieuwe-hoofdtrainer-weg-bij-sc-heerenveen",
    "ere_heer": "https://nl.wikipedia.org/wiki/Sc_Heerenveen_in_het_seizoen_2026/27_(mannen)",
    "malaga": "https://www.merchanendirecto.es/fumata-blanca-funes-sera-el-nuevo-entrenador-del-malaga-cf/",
    "depor": "https://es.wikipedia.org/wiki/Antonio_Hidalgo_Morilla",
}

# Coach-led review of the clubs first filed as pragmatic (19 Oct 2026). Coach names come from
# the season lists above; the approach comes from each coach's track record at previous clubs.
# Philosophy wins over this season's numbers (a Simeone side with the ball is still Simeone's).
COACH_PICKS = {
    # Premier League
    "Chelsea": ("possession", "medium", "Xabi Alonso", "Leverkusen's unbeaten title side: 3-4-2-1, positional play, long spells on the ball and a hard counter-press", "pl_list"),
    "Everton": ("low_block", "medium", "David Moyes", "Compact 4-4-2 / 4-2-3-1, defend deep, counters and set pieces (West Ham's Conference League win)", "pl_list"),
    "Fulham": ("possession", "low", "Álvaro Arbeloa", "Real Madrid academy coach: proactive 4-3-3 on the ball; 57% possession so far", "pl_list"),
    "Hull City": ("low_block", "medium", "Sergej Jakirović", "Dinamo Zagreb and Hull: solid shape first, direct transitions; 32% possession", "pl_list"),
    "Leeds United": ("pragmatic", "medium", "Daniel Farke", "Possession sides in the Championship (Norwich, Leeds), noticeably more compact and cautious in the Premier League", "pl_list"),
    "Sunderland": ("pragmatic", "medium", "Régis Le Bris", "Structured, patient build-up with a young squad at Lorient; compact mid-block since promotion", "pl_list"),
    "Aston Villa": ("pragmatic", "high", "Unai Emery", "Plans for each opponent: high line and offside trap, baits the press, game management", "pl_list"),
    "Liverpool": ("press", "high", "Andoni Iraola", "Bournemouth's man-to-man press: relentless, vertical, high energy", "pl_list"),
    "Manchester United": ("possession", "medium", "Michael Carrick", "Middlesbrough under him: possession-based 4-2-3-1, patient build-up; 18.7 shots a game", "pl_list"),
    "Nottingham Forest": ("press", "medium", "Oliver Glasner", "Frankfurt and Palace: 3-4-2-1, aggressive press and fast transitions", "pl_list"),
    "Newcastle United": ("press", "high", "Matthias Jaissle", "Red Bull school (Salzburg): gegenpress and vertical attacks", "pl_list"),
    "Brentford": ("direct", "high", "Keith Andrews", "Former set-piece coach; long throws, set pieces and directness remain the identity", "pl_list"),
    # La Liga
    "Atlético Madrid": ("low_block", "high", "Diego Simeone", "Simeone's philosophy: compact block, intensity, strike on the break, even with more of the ball this season", None),
    "Alavés": ("low_block", "medium", "Quique Sánchez Flores", "Organised, compact, defend first, counter: his trademark at Getafe, Watford and Sevilla", "liga_list"),
    "Celta Vigo": ("possession", "medium", "Claudio Giráldez", "Academy-built positional play, back-three build-up, plays out from the back", "liga_list"),
    "Deportivo La Coruña": ("pragmatic", "low", "Antonio Hidalgo", "Promoted with a compact, balanced side; style little documented", "depor"),
    "Elche": ("press", "medium", "Martín Anselmi", "Cruz Azul and Porto: 3-4-3, aggressive man-oriented press, high line", "liga_list"),
    "Levante": ("pragmatic", "low", "Luís Castro", "Possession 4-3-3 at Shakhtar and Botafogo; sits deeper with a survival squad", "liga_list"),
    "Málaga": ("pragmatic", "low", "Juanfran Funes", "First top-flight job after promotion; style not documented yet", "malaga"),
    "Real Sociedad": ("press", "medium", "Pellegrino Matarazzo", "Red Bull school (Stuttgart, Hoffenheim): high press, vertical attacks", "liga_list"),
    "Valencia": ("press", "medium", "Carlos Corberán", "Bielsa disciple: man-oriented pressing, intensity, runners (Huddersfield, West Brom)", "liga_list"),
    # Ligue 1
    "Angers": ("pragmatic", "low", "Stéphane Gilli", "New in the job; style not documented yet", "l1_list"),
    "Lille": ("pragmatic", "medium", "Davide Ancelotti", "Botafogo: balanced, adaptable, game management, like his father", "l1_list"),
    "Lorient": ("low_block", "medium", "Alexandre Dujeux", "Angers' survival side: compact low block, counters", "l1_list"),
    "Lyon": ("possession", "medium", "Paulo Fonseca", "Roma, Lille, Milan: proactive 4-2-3-1, keeps the ball, attacks with numbers", "l1_list"),
    "Marseille": ("pragmatic", "medium", "Bruno Genesio", "Rennes and Lille: adaptable, offensive when he can, pragmatic when he must", "l1_list"),
    "Monaco": ("possession", "medium", "Filipe Luís", "Flamengo: ball dominance, positional play, high counter-press", "l1_list"),
    "Nice": ("low_block", "medium", "Olivier Pantaloni", "Ajaccio and Lorient: compact, defend first, strike on the break", "l1_list"),
    "Toulouse": ("pragmatic", "low", None, "New coach not named in the sources found; 15.6 fouls a game", None),
    "Troyes": ("pragmatic", "low", None, "Kept their promotion coach; 39% possession", "l1_list"),
    # Serie A
    "Bologna": ("pragmatic", "medium", "Domenico Tedesco", "Leipzig and Belgium: flexible shapes, compact, picks his moments to press", "sa_list"),
    "Fiorentina": ("chaos", "medium", "Fabio Grosso", "Frosinone and Sassuolo: attacking 4-3-3, open games; 16.6 shots for, 2.4 conceded", "sa_list"),
    "Genoa": ("possession", "low", "Daniele De Rossi", "Roma: positional 4-3-3, plays through the lines; now a back three", "sa_list"),
    "Lazio": ("pragmatic", "medium", "Gennaro Gattuso", "Napoli's possession 4-3-3, later more pragmatic (Marseille, Hajduk, Italy)", "sa_list"),
    "Napoli": ("pragmatic", "high", "Massimiliano Allegri", "The archetype: control the game, not the ball; win 1-0", "sa_list"),
    "Parma": ("low_block", "medium", "Carlos Cuesta", "Arteta's former assistant with possession ideas, but a deep, compact Parma; 42% possession, 18 shots conceded", "sa_list"),
    "Torino": ("pragmatic", "low", "Ignazio Abate", "Proactive 3-5-2 at Juve Stabia; first Serie A season", "sa_list"),
    "Udinese": ("direct", "medium", "Kosta Runjaić", "Legia and Udinese: 3-5-2, physical, direct, quick transitions", "sa_list"),
    "Venezia": ("chaos", "medium", "Giovanni Stroppa", "Attacking 3-5-2 (Crotone, Venezia promotions); 17.6 shots conceded", "sa_list"),
    # Bundesliga
    "SC Freiburg": ("pragmatic", "high", "Julian Schuster", "Freiburg's model: compact 4-4-2 out of possession, efficient, strong set pieces", "bl_kicker"),
    "SC Paderborn": ("pragmatic", "low", "Ralf Kettemann", "Style little documented at this level", None),
    # Eredivisie
    "SC Heerenveen": ("pragmatic", "low", "Robin Veldman", "Style little documented", "ere_heer"),
    "Telstar": ("pragmatic", "low", "Henk Brugge", "First head-coach job; style not documented yet", "ere_telstar"),
    # Primeira Liga
    "Arouca": ("possession", "medium", "Vasco Seabra", "Arouca's ball-playing, positional style", "pt_coaches"),
    "C.D. Nacional": ("possession", "low", "João Gião", "Sporting B: Sporting-school 3-4-3 on the ball", "pt_coaches"),
    "Casa Pia": ("possession", "low", "Filipe Coelho", "BlueCo staff (Chelsea, Strasbourg): possession-based", "pt_coaches"),
    "Estoril": ("low_block", "medium", "Vasco Matos", "Santa Clara: compact, very hard to break down, counters", "pt_coaches"),
    "Famalicão": ("possession", "medium", "Carlos Carvalhal", "Braga, Swansea: build-up and positional play", "pt_coaches"),
    "Gil Vicente": ("pragmatic", "low", "Luís Pinto", "Style little documented", "pt_coaches"),
    "Porto": ("pragmatic", "medium", "Francesco Farioli", "Nice and Ajax: control and defensive solidity, adapts to the squad", "pt_coaches"),
    "Rio Ave": ("pragmatic", "low", "Sotiris Sylaidopoulos", "Style little documented", "pt_coaches"),
    "Santa Clara": ("direct", "medium", "Petit", "Boavista, Paços: intensity, physical duels, compact", "pt_coaches"),
    "Sporting CP": ("possession", "medium", "Rui Borges", "Title-winning 3-4-3 on the ball", "pt_coaches"),
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

# Deeper research, 19 Oct 2026: national press, club announcements, coach bios and local
# outlets for every club below high confidence. (L'Équipe, France Football, So Foot and
# Ouest-France block automated access, so French clubs rely on other outlets quoting them.)
DEEP_PICKS = {
    # Ligue 1
    "Auxerre": ("press", "medium", "Will Still", "Pressing, vertical 4-3-3 identity from Reims; switched to a 5-4-1 early on to tighten up", "https://ligue1.com/en/articles/l1_article_5488-will-still-hungry-as-new-auxerre-era-begins"),
    "Strasbourg": ("press", "medium", "Hugo Oliveira", "Takes the initiative: possession, high tempo, intense press, direct down the wings; weak when forced into a low block", "https://www.rcstrasbourgalsace.fr/en/hugo-oliveira-appointed-head-coach-of-racing-club-de-strasbourg-alsace/"),
    "Lens": ("press", "high", "Dino Toppmöller", "Intense, offensive football and a high press; wants to keep the ball to save energy for pressing", "https://www.rclens.fr/fr/rclens-conference-de-presse-presentation-dino-toppmoller-20260616"),
    "Toulouse": ("possession", "medium", "Jens Berthel Askou", "Expansive, attacking football at Motherwell, with a club record for clean sheets", "https://www.skysports.com/football/news/36621/13546645/jens-berthel-askou-motherwell-boss-leaves-to-take-charge-at-toulouse-following-successful-debut-season-in-premiership"),
    "Le Havre": ("press", "medium", "Didier Digard", "'My style is offensive': pressing, courage, risk-taking; fragile when the team pushes up", "https://ligue1.com/en/articles/l1_article_560-le-havre-manager-didier-digard-my-style-is-offensive-it-reflects-my-personality"),
    "Brest": ("direct", "medium", "Julien Lachuer", "Stable shape, simple pressing triggers, less risky build-up, a target man up front", "https://www.coeur-de-gone.fr/2026/06/stade-brestois-julien-lachuer-va-devenir-le-nouvel-entraineur-un-choix-fort-pour-lancer-un-nouveau-cycle/"),
    "Le Mans": ("press", "medium", "Patrick Videira", "Fluid rotations over fixed systems ('football is chess'), an efficient press, compact", "https://ligue1.com/en/articles/l1_article_5592-who-is-patrick-videira-le-mans-fast-rising-coach"),
    "Troyes": ("pragmatic", "medium", "Stéphane Dumont", "'Not dogmatic, adapts to the players he has'; rigour and Premier League-style intensity", "https://www.footmercato.net/a8736963809579446176-stephane-dumont-lhomme-derriere-lincroyable-renouveau-de-troyes"),
    "Angers": ("chaos", "medium", "Stéphane Gilli", "Openly attacking and forward-looking, accepts mistakes as part of the plan (Paris FC before)", "https://antichambre.eu/stephane-gilli-angers-sco-on-manque-defficacite-dans-les-deux-surfaces/"),
    "Nice": ("low_block", "medium", "Olivier Pantaloni", "His Lorient sat in a very marked low block and played direct", "https://morning-foot.com/ligue-1/nice/pantaloni-ogc-nice-entraineur-analyse-tactique-data-scout/"),
    "Lorient": ("direct", "medium", "Alexandre Dujeux", "Angers' survival sides: intense, combative, duel-heavy on a small budget", "https://morning-foot.com/ligue-1/lorient/dujeux-lorient-angers-comparaison-style-jeu-data-scout/"),
    "Monaco": ("possession", "high", "Filipe Luís", "'My game model is offensive, dominant and based on a high press'; 62% possession at Flamengo", "https://www.asmonaco.com/fr/news/pressing-haut-possession-59-3-les-chiffres-cles-du-coach-filipe-luis"),
    "Rennes": ("press", "medium", "Franck Haise", "His Lens: intense 3-4-2-1, aggressive wing-backs; 18 shots a game at Rennes", "https://en.wikipedia.org/wiki/Franck_Haise"),
    # Primeira Liga
    "Braga": ("possession", "high", "Carlos Vicens", "Former Guardiola assistant: associative play, mobility, many players around the ball", "https://tvi.iol.pt/noticias/sp-braga/carlos-vicens/carlos-vicens-e-a-epoca-do-sp-braga-temos-de-estar-satisfeitos"),
    "Famalicão": ("possession", "high", "Carlos Carvalhal", "Rival coach Rui Borges: 'one of the teams with the most possession, they like to dominate'", "https://www.dn.pt/desporto/rui-borges-exige-sporting-ligado-em-famalico-o-nosso-grande-objetivo-o-campeonato"),
    "Arouca": ("possession", "medium", "Vasco Seabra", "'Dominant with the ball, selective with the press, jumping at the right moments'", "https://www.record.pt/futebol/futebol-nacional/liga-betclic/arouca/detalhe/vasco-seabra-e-o-estoril-arouca-o-jogo-comeca-num-quadro-em-branco-e-temos-de-ser-nos-a-escrever-nele"),
    "Marítimo": ("direct", "medium", "Mitchell van der Gaag", "Built on defensive organisation and winning duels", "https://www.record.pt/futebol/futebol-nacional/liga-betclic/maritimo/detalhe/van-der-gaag-apos-maritimo-voltar-a-pontuar-quebramos-essa-sequencia-e-isso-foi-importante"),
    "Vitória SC": ("press", "medium", "Tiago Margarido", "'Open-chested and offensive', aggressive; 17.8 shots a game", "https://www.abola.pt/noticias/tiago-margarido-e-o-derbi-inspiracao-no-jogo-que-o-vitoria-fez-ha-dois-anos-2026083011540317383"),
    "Moreirense": ("low_block", "medium", "Vasco Botelho da Costa", "Wants more of the ball, but defends lower against stronger sides; 36% possession", "https://www.record.pt/futebol/futebol-nacional/liga-betclic/moreirense/amp/vasco-botelho-da-costa-queremos-ser-uma-equipa-com-capacidade-para-lutar-pela-vitoria-em-qualquer-jogo"),
    "Casa Pia": ("pragmatic", "low", "Filipe Coelho", "No documented approach yet; the side defended in a back five last season", "https://www.abola.pt/noticias/casa-pia-em-alpendorada-nao-vamos-olhar-para-este-jogo-de-forma-diferente-2026101714334966270"),
    "Rio Ave": ("pragmatic", "low", "Sotiris Silaidopoulos", "Promises 'aggression and passion'; moved from a 3-4-3 to a 4-2-3-1", "https://observador.pt/2026/05/15/silaidopoulos-promete-rio-ave-com-agressividade-e-paixao-frente-ao-casa-pia-e-ja-planeia-a-proxima-temporada/"),
    "Sporting CP": ("possession", "medium", "Rui Borges", "Switched to a 4-3-3 this season with new principles of play; 55% possession", "https://www.record.pt/futebol/futebol-nacional/liga-betclic/sporting/detalhe/a-nova-formula-do-sporting-como-rui-borges-espera-potenciar-o-4x3x3-e-dar-maior-liberdade-a-doumbia"),
    # La Liga
    "Athletic Club": ("press", "high", "Edin Terzić", "Very aggressive press, very quick in possession, fast transitions (Dortmund)", "https://www.futbolfantasy.com/laliga/noticias/148063-analisis-de-edin-terzic-presion-con-sentido-y-flexibilidad-para-reactivar-al-athletic"),
    "Sevilla": ("direct", "high", "Luis García Plaza", "Compact and disciplined; the ball is a tool: direct play, crosses, quick transitions", "https://www.futbolfantasy.com/laliga/noticias/141624-luis-garcia-plaza-sobriedad-y-ambicion-para-el-sevilla-filosofia-idea-y-estilo-de-juego"),
    "Osasuna": ("low_block", "medium", "Luis Miguel Ramis", "Best defence in Segunda with Burgos; defends well in his half, attacks fast off mistakes", "https://www.noticiasdenavarra.com/osasuna/2026/06/10/llega-ramis-osasuna-entrenador-sobrio-orden-11182099.html"),
    "Real Betis": ("press", "medium", "Manuel Pellegrini", "Moved from a patient game to transitions with runners; struggles against deep blocks", "https://beticismo.substack.com/p/las-posibilidades-tacticas-del-betis"),
    "Levante": ("press", "medium", "Luís Castro", "High press and quick transitions down the flanks; calls himself an offensive coach", "https://www.futbolfantasy.com/laliga/noticias/137802-luis-castro-se-presenta-y-habla-de-identidad-proyecto-y-ambicion-para-reactivar-al-levante"),
    "Espanyol": ("direct", "low", "Manolo González", "Sources conflict (proactive model v intense and balanced); 16 fouls a game", "https://el1900.com/como-jugara-espanyol-manolo-gonzalez/"),
    "Getafe": ("direct", "high", "José Bordalás", "Bordalás: duels, intensity, direct play and set pieces; 39% possession, 14 fouls a game", "https://www.eldesmarque.com/futbol/liga-1a-division/20260618/banquillos-laliga-2026-2027-nuevos-entrenadores_18_019482771.html"),
    # Serie A
    "Monza": ("press", "high", "Ivan Jurić", "Man-to-man pressing all over the pitch, immediate verticality, concedes a lot", "https://www.pianetalecce.it/news/27472072198/lecce-monza-numeri-e-caratteristiche-della-squadra-di-juric"),
    "Sassuolo": ("possession", "medium", "Alberto Aquilani", "Builds from the back, 4-3-3 with a deep playmaker; the keeper is the first playmaker", "https://ultimouomo.com/guida-al-sassuolo-serie-a-2026-27-possibile-formazione-fantacalcio-come-giochera"),
    "Lecce": ("low_block", "medium", "Eusebio Di Francesco", "4-3-3 built on wingers, but a compact 5-3-2 low block without the ball", "https://www.sportellate.it/2026/07/29/di-francesco-scuse-lecce/"),
    "Cagliari": ("low_block", "medium", "Fabio Pisacane", "'Vertical football': mixes short build-up and direct balls; 38% possession, 0.5 conceded", "https://www.gianlucadimarzio.com/news-calcio/cagliari-pisacane-il-calcio-verticale-nato-sconfitto-malattia-493858"),
    "Parma": ("low_block", "low", "Carlos Cuesta (reportedly dismissed)", "Deep and compact under Cuesta, who was reportedly dismissed after 5 matchdays; style may change", "https://www.pazzidifanta.com/news/parma-genoa-formazioni-ufficiali-quinta-giornata-serie-a-2026-27-459444"),
    # Bundesliga
    "Bayer Leverkusen": ("possession", "high", "Carles Martínez Novell", "La Masia school: modern possession football, controlled build-up, aggressive counter-press", "https://www.bundesliga.com/de/bundesliga/news/carles-martinez-novell-bayer-04-leverkusen-trainer-funf-dinge-37695"),
    "Union Berlin": ("press", "medium", "Mauro Lustrinelli", "'The end of pragmatism': courage, offensive solutions, high press plus an active block", "https://www.sportschau.de/regional/rbb/rbb-union-berlin-strategiewechsel-mit-neuem-trainer-lustrinelli-100.html"),
    "VfB Stuttgart": ("possession", "medium", "Sebastian Hoeneß", "Possession-based positional play since 2023; 57% possession", "https://www.kicker.de/vfb-stuttgart/team-trainer"),
    "Werder Bremen": ("press", "medium", "Daniel Thioune", "Fast, aggressive transition football: win it early, 'depth before width'", "https://www.deichstube.de/news/werder-bremen-daniel-thioune-wie-spielt-neuer-trainer-spielstil-analyse-bundesliga-taktik-formation-zr-94158894.html"),
    "Hamburger SV": ("pragmatic", "medium", "Merlin Polzin", "Tailors the plan to each opponent rather than one fixed idea", "https://moinvolkspark.de/artikel/von-ausfaellen-und-anpassung-polzins-hsv-rezept"),
    "Schalke 04": ("press", "medium", "Miron Muslić", "'Our game is defined by aggression and intensity', an active style", "https://pt.soccerway.com/noticias/futebol-2-bundesliga-miron-muslic-quer-levar-o-schalke-de-volta-ao-topo-e-um-gigante-do-futebol/0pGniBLM"),
    "1. FC Köln": ("possession", "low", "René Wagner", "4-2-3-1 that is active on the ball, data-driven", "https://www.getfootballnewsgermany.com/2026/bundesliga-koln-preview-26/"),
    "FC Augsburg": ("low_block", "low", "Manuel Baum", "Defensive organisation first; tried a 3-4-3 in pre-season", "https://www.getfootballnewsgermany.com/2026/bundesliga-augsburg-preview-26/"),
    # Eredivisie
    "Feyenoord": ("press", "high", "Giovanni van Bronckhorst", "High intensity, aggressive pressing, tempo (learnt as Slot's assistant at Liverpool)", "https://1908.nl/artikelen/van-bronckhorst-schetst-gewenste-speelstijl-altijd-aan-staan"),
    "Go Ahead Eagles": ("chaos", "medium", "Joseph Oosting", "Plays its own game whoever the opponent, creates a lot, concedes a lot", "https://www.vi.nl/pro/wel-creeren-niet-belonen-go-ahead-eagles-doet-zichzelf-tekort"),
    "NEC": ("possession", "medium", "Dick Schreuder", "Praised for an attractive playing philosophy; 59% possession", "https://www.forzanec.nl/nieuws/oosting-kijkt-met-bewondering-naar-opmars-nec/"),
    # Premier League
    "Coventry City": ("pragmatic", "medium", "Frank Lampard", "Back-three build-up, short and direct mixed, wide press; more compact lately", "https://www.squawka.com/en/features/tactical-analysis-coventry-finding-their-feet/"),
}

# Coaches named in the season lists, for clubs whose style still rests on stats.
COACHES = {
    "AZ": "Leeroy Echteld", "FC Twente": "John van den Brom", "FC Groningen": "Dick Lukkien",
    "Sparta Rotterdam": "Rogier Meijer", "Utrecht": "Anthony Correia", "Excelsior": "Ruben den Uil",
    "PEC Zwolle": "Henry van der Vegt", "Fortuna Sittard": "Danny Buijs", "Willem II": "John Stegeman",
    "Ipswich Town": "Gary O'Neil", "Elversberg": "Vincent Wagner", "Racing Santander": "José Alberto López",
    "Rayo Vallecano": "Beñat San José", "Acad. Viseu": "Bruno Pinheiro", "Alverca": "Sérgio Ferreira",
    "Estrela": "Pepa", "Udinese": "Kosta Runjaić",
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
        if team in DEEP_PICKS:
            profile, conf, coach, why, url = DEEP_PICKS[team]
            clubs[team] = {"league": league, "profile": profile, "confidence": conf, "coach": coach,
                           "why": why, "source": url, "basis": "research (deeper pass)", "stats": numbers}
        elif team in PICKS or team in COACH_PICKS:
            profile, conf, coach, why, src = COACH_PICKS.get(team) or PICKS[team]
            data_profile, _ = from_stats(s)
            if conf == "medium" and data_profile == profile and src:
                conf = "high"  # the source and the stats agree
            clubs[team] = {"league": league, "profile": profile, "confidence": conf, "coach": coach,
                           "why": why, "source": S.get(src), "basis": "research" if src else "club identity + stats",
                           "stats": numbers}
        elif league:
            profile, why = from_stats(s)
            clubs[team] = {"league": league, "profile": profile, "confidence": "low", "coach": COACHES.get(team),
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
