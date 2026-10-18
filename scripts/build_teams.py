"""Build teams.csv: one canonical row per club found in rivalries.json and records.json.

Aliases are hand-written spelling variants (official names, short names,
local-language names). They are NOT verified provider names: match_teams.py
checks them against each provider's real team list and reports misses.
"""
import csv, json, re

COUNTRY = {"Premier League": "England", "La Liga": "Spain", "Serie A": "Italy",
           "Bundesliga": "Germany", "Ligue 1": "France", "Eredivisie": "Netherlands",
           "Primeira Liga": "Portugal"}

ALIASES = {
 # England
 "Manchester United": ["Manchester United FC", "Man United", "Man Utd"],
 "Manchester City": ["Manchester City FC", "Man City"],
 "Liverpool": ["Liverpool FC"], "Everton": ["Everton FC"],
 "Arsenal": ["Arsenal FC"], "Chelsea": ["Chelsea FC"],
 "Tottenham Hotspur": ["Tottenham Hotspur FC", "Tottenham", "Spurs"],
 "West Ham United": ["West Ham United FC", "West Ham"],
 "Newcastle United": ["Newcastle United FC", "Newcastle"],
 "Leeds United": ["Leeds United FC", "Leeds"],
 "Aston Villa": ["Aston Villa FC"], "Crystal Palace": ["Crystal Palace FC"],
 "Brighton & Hove Albion": ["Brighton & Hove Albion FC", "Brighton"],
 "Wolverhampton Wanderers": ["Wolverhampton Wanderers FC", "Wolves"],
 "West Bromwich Albion": ["West Bromwich Albion FC", "West Brom"],
 "Nottingham Forest": ["Nottingham Forest FC", "Nott'm Forest"],
 "Leicester City": ["Leicester City FC", "Leicester"],
 "AFC Bournemouth": ["Bournemouth"], "Fulham": ["Fulham FC"], "Brentford": ["Brentford FC"],
 "Sunderland": ["Sunderland AFC"], "Southampton": ["Southampton FC"],
 "Burnley": ["Burnley FC"], "Ipswich Town": ["Ipswich Town FC", "Ipswich"],
 "Norwich City": ["Norwich City FC", "Norwich"],
 # Spain
 "Barcelona": ["FC Barcelona", "Barça"], "Real Madrid": ["Real Madrid CF"],
 "Atlético Madrid": ["Club Atlético de Madrid", "Atletico Madrid", "Atlético de Madrid"],
 "Athletic Club": ["Athletic Bilbao", "Athletic Club Bilbao"],
 "Real Sociedad": ["Real Sociedad de Fútbol"], "Real Betis": ["Real Betis Balompié", "Betis"],
 "Sevilla": ["Sevilla FC"], "Espanyol": ["RCD Espanyol", "RCD Espanyol de Barcelona"],
 "Valencia": ["Valencia CF"], "Levante": ["Levante UD"], "Villarreal": ["Villarreal CF"],
 "Celta Vigo": ["RC Celta de Vigo", "Celta"],
 "Deportivo La Coruña": ["RC Deportivo La Coruña", "Deportivo", "Deportivo de La Coruña"],
 "Real Oviedo": ["Oviedo"], "Racing Santander": ["Real Racing Club de Santander"], "Sporting Gijón": ["Real Sporting de Gijón", "Sporting de Gijón"],
 "Getafe": ["Getafe CF"], "Leganés": ["CD Leganés"], "Girona": ["Girona FC"],
 "Osasuna": ["CA Osasuna"], "Alavés": ["Deportivo Alavés"], "Elche": ["Elche CF"],
 "Granada": ["Granada CF"], "Málaga": ["Málaga CF"], "Almería": ["UD Almería"],
 "Las Palmas": ["UD Las Palmas"], "Tenerife": ["CD Tenerife"], "Eibar": ["SD Eibar"],
 "Real Zaragoza": ["Zaragoza"], "Huesca": ["SD Huesca"],
 # Italy
 "Inter": ["FC Internazionale Milano", "Inter Milan", "Internazionale"],
 "AC Milan": ["Milan"], "Juventus": ["Juventus FC"], "Roma": ["AS Roma"],
 "Lazio": ["SS Lazio"], "Napoli": ["SSC Napoli"], "Torino": ["Torino FC"],
 "Genoa": ["Genoa CFC"], "Sampdoria": ["UC Sampdoria"], "Fiorentina": ["ACF Fiorentina"],
 "Bologna": ["Bologna FC 1909"], "Atalanta": ["Atalanta BC"], "Parma": ["Parma Calcio 1913"],
 "Hellas Verona": ["Hellas Verona FC", "Verona"], "Cagliari": ["Cagliari Calcio"],
 "Empoli": ["Empoli FC"], "Lecce": ["US Lecce"], "Como": ["Como 1907"], "Monza": ["AC Monza"],
 "Sassuolo": ["US Sassuolo Calcio"], "Cremonese": ["US Cremonese"], "Pisa": ["AC Pisa 1909"],
 "Venezia": ["Venezia FC"], "Udinese": ["Udinese Calcio"],
 # Germany
 "Bayern Munich": ["FC Bayern München", "Bayern München", "Bayern"],
 "Borussia Dortmund": ["BV Borussia 09 Dortmund", "Dortmund", "BVB"],
 "Schalke 04": ["FC Schalke 04", "Schalke"],
 "Borussia Mönchengladbach": ["Borussia Monchengladbach", "Mönchengladbach", "Gladbach"],
 "1. FC Köln": ["FC Köln", "Köln", "Cologne"], "Bayer Leverkusen": ["Bayer 04 Leverkusen", "Leverkusen"],
 "Hamburger SV": ["Hamburg", "HSV"], "Werder Bremen": ["SV Werder Bremen"],
 "FC St. Pauli": ["St. Pauli", "FC St. Pauli 1910"],
 "Union Berlin": ["1. FC Union Berlin"], "Hertha BSC": ["Hertha Berlin"],
 "VfB Stuttgart": ["Stuttgart"], "SC Freiburg": ["Sport-Club Freiburg", "Freiburg"],
 "Eintracht Frankfurt": ["Frankfurt"], "VfL Bochum": ["VfL Bochum 1848", "Bochum"],
 "FC Augsburg": ["Augsburg"], "1. FC Nürnberg": ["Nürnberg", "Nuremberg"],
 "Greuther Fürth": ["SpVgg Greuther Fürth"], "Darmstadt 98": ["SV Darmstadt 98"],
 "Fortuna Düsseldorf": ["Düsseldorf"], "Arminia Bielefeld": ["DSC Arminia Bielefeld"],
 "Hannover 96": ["Hannover"], "Hansa Rostock": ["FC Hansa Rostock"],
 # France
 "Paris Saint-Germain": ["Paris Saint-Germain FC", "PSG", "Paris SG"],
 "Marseille": ["Olympique de Marseille", "Olympique Marseille", "OM"], "Lyon": ["Olympique Lyonnais", "OL"],
 "Saint-Étienne": ["AS Saint-Étienne", "Saint-Etienne"], "Lens": ["Racing Club de Lens", "RC Lens"],
 "Lille": ["Lille OSC", "LOSC"], "Monaco": ["AS Monaco FC", "AS Monaco"], "Nice": ["OGC Nice"],
 "Nantes": ["FC Nantes"], "Rennes": ["Stade Rennais FC 1901", "Stade Rennais"],
 "Brest": ["Stade Brestois 29"], "Lorient": ["FC Lorient"], "Guingamp": ["EA Guingamp"],
 "Angers": ["Angers SCO"], "Bordeaux": ["FC Girondins de Bordeaux", "Girondins de Bordeaux"],
 "Toulouse": ["Toulouse FC"], "Metz": ["FC Metz"], "Nancy": ["AS Nancy Lorraine"],
 "Strasbourg": ["RC Strasbourg Alsace", "RC Strasbourg"], "Le Havre": ["Le Havre AC"],
 "Caen": ["Stade Malherbe Caen", "SM Caen"], "Auxerre": ["AJ Auxerre"], "Troyes": ["ESTAC Troyes", "Troyes AC", "ES Troyes AC"],
 "Reims": ["Stade de Reims"], "Montpellier": ["Montpellier HSC"], "Paris FC": ["Paris FC"],
 # Netherlands
 "Ajax": ["AFC Ajax"], "Feyenoord": ["Feyenoord Rotterdam"], "PSV": ["PSV Eindhoven", "PSV"],
 "AZ": ["AZ Alkmaar"], "FC Twente": ["FC Twente '65", "Twente"], "Heracles Almelo": ["Heracles"],
 "FC Groningen": ["Groningen"], "SC Heerenveen": ["sc Heerenveen", "Heerenveen"],
 "Sparta Rotterdam": ["Sparta"], "Excelsior": ["SBV Excelsior", "Excelsior Rotterdam"],
 "PEC Zwolle": ["Zwolle"], "Go Ahead Eagles": ["GA Eagles"], "NAC Breda": ["NAC"],
 "Willem II": ["Willem II Tilburg"], "Telstar": ["Telstar 1963"], "SC Cambuur": ["SC Cambuur-Leeuwarden", "Cambuur"], "Fortuna Sittard": ["Fortuna"],
 # Portugal
 "Benfica": ["SL Benfica", "Sport Lisboa e Benfica"], "Porto": ["FC Porto"],
 "Sporting CP": ["Sporting Clube de Portugal", "Sporting Lisbon", "Sporting"],
 "Braga": ["SC Braga", "Sporting Braga", "Sporting Clube de Braga"], "Vitória SC": ["Vitória Guimarães", "Vitoria Guimaraes"],
 "Boavista": ["Boavista FC"], "Marítimo": ["CS Marítimo", "Maritimo"], "Rio Ave": ["Rio Ave FC"],
}

# The rivalries file says "Bournemouth"; fold it into the official canonical name.
RENAME = {"Bournemouth": "AFC Bournemouth", "Deportivo": "Deportivo La Coruña"}

def strip(s):
    return re.sub(r"\s+", " ", s).strip()

clubs = {}
def add(name, country):
    name = RENAME.get(name, name)
    clubs.setdefault(name, country)

for r in json.load(open("data/rivalries.json", encoding="utf-8")):
    for side in ("club_a", "club_b"):
        add(r[side], COUNTRY[r["league"]])

for r in json.load(open("data/records.json", encoding="utf-8")):
    if r["subject"] == "team" and r["competition"] in COUNTRY:
        for name in r["holder"].split("/"):
            add(strip(name), COUNTRY[r["competition"]])

# Keep provider IDs already filled by match_teams.py.
ID_COLUMNS = ("football_data_id", "api_football_id", "transfermarkt_id")
try:
    old = {r["canonical_name"]: r for r in csv.DictReader(open("data/teams.csv", encoding="utf-8"))}
except FileNotFoundError:
    old = {}

rows = []
for name in sorted(clubs, key=lambda n: (clubs[n], n)):
    rows.append({"canonical_name": name, "country": clubs[name],
                 "aliases": "|".join(ALIASES.get(name, [])),
                 **{c: old.get(name, {}).get(c, "") for c in ID_COLUMNS}})

with open("data/teams.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)

print(len(rows), "clubs;", sum(1 for r in rows if r["aliases"]), "with aliases")
