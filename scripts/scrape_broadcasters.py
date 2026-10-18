"""Where to watch: TV/streaming rights per competition and country.

Sources:
  Wikipedia broadcaster tables (official MediaWiki API, 2 seconds apart) for the
  competitions that have one: Champions League, Premier League (overseas), La Liga,
  Serie A, Ligue 1.
  data/broadcasters_manual.json: researched entries, each with its own source, for the
  gaps (domestic rights, Bundesliga, Eredivisie, Primeira Liga, Europa/Conference League).
  Manual entries win over Wikipedia for the same competition and country.
  The system time-zone tables (zone.tab, iso3166.tab) for time zone -> country.

Writes data/broadcasters.json, which the site reads. Rights are per competition, not per
match: a match can still be on a different channel, so the site says "usually on".

  python scripts/scrape_broadcasters.py
  python scripts/scrape_broadcasters.py --max-age 7   # skip if refreshed in the last 7 days
"""
import argparse, json, re, sys, time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from fd_client import ROOT

API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "personal-match-recommender/0.1 (personal use; github.com/matheodecarvalho-pixel/match-recommender)"}
OUT = ROOT / "data" / "broadcasters.json"
MANUAL = ROOT / "data" / "broadcasters_manual.json"
ZONEINFO = Path("/usr/share/zoneinfo")

PAGES = {
    "Champions League": "List of UEFA Champions League broadcasters",
    "Premier League": "List of Premier League overseas broadcasters",
    "La Liga": "List of La Liga broadcasters",
    "Serie A": "List of Serie A broadcasters",
    "Ligue 1": "Ligue 1",
}

# Wikipedia country names that differ from iso3166.tab.
ALIASES = {
    "United Kingdom": "GB", "UK": "GB", "Great Britain": "GB", "England": "GB", "Scotland": "GB",
    "Wales": "GB", "Northern Ireland": "GB", "United States": "US", "USA": "US",
    "Russia": "RU", "South Korea": "KR", "North Korea": "KP", "Iran": "IR", "Syria": "SY",
    "Vietnam": "VN", "Laos": "LA", "Taiwan": "TW", "Czech Republic": "CZ", "Czechia": "CZ",
    "Moldova": "MD", "Bolivia": "BO", "Venezuela": "VE", "Tanzania": "TZ", "Brunei": "BN",
    "Macau": "MO", "Macao": "MO", "Hong Kong": "HK", "Ivory Coast": "CI", "Côte d'Ivoire": "CI",
    "Timor Leste": "TL", "Republic of Ireland": "IE", "Ireland": "IE", "Bosnia and Herzegovina": "BA", "Kosovo": "XK",
    "North Macedonia": "MK", "Turkey": "TR", "Türkiye": "TR", "Palestine": "PS", "Cape Verde": "CV",
    "DR Congo": "CD", "Democratic Republic of the Congo": "CD", "Republic of the Congo": "CG",
    "Eswatini": "SZ", "East Timor": "TL", "Timor-Leste": "TL", "Vatican City": "VA",
    "Micronesia": "FM", "Netherlands": "NL", "The Netherlands": "NL", "Myanmar": "MM",
    "Sint Maarten": "SX", "Curaçao": "CW", "Saint Kitts and Nevis": "KN", "Saint Lucia": "LC",
    "Saint Vincent and the Grenadines": "VC", "Trinidad and Tobago": "TT", "Antigua and Barbuda": "AG",
}
# Region rows expanded to countries.
REGIONS = {
    "Sub-Saharan Africa": "AO BF BI BJ BW CD CF CG CI CM CV DJ ER ET GA GH GM GN GQ GW KE LR LS MG ML MR MU MW MZ NA NE NG RW SC SL SN SO SS ST SZ TD TG TZ UG ZA ZM ZW",
    "Middle East and North Africa": "AE BH DZ EG IQ JO KW LB LY MA OM PS QA SA SD SY TN YE",
    "MENA": "AE BH DZ EG IQ JO KW LB LY MA OM PS QA SA SD SY TN YE",
    "Caribbean": "AG AI AW BB BQ BS CW DM DO GD HT JM KN KY LC MS SX TC TT VC VG",
    "Latin America": "AR BO BR CL CO CR CU DO EC GT HN MX NI PA PE PY SV UY VE",
    "Central America": "BZ CR GT HN NI PA SV",
    "South America": "AR BO BR CL CO EC GY PE PY SR UY VE",
    "Balkans": "AL BA HR ME MK RS SI XK",
    "Former Yugoslavia": "BA HR ME MK RS SI XK",
    "Baltics": "EE LT LV", "Baltic states": "EE LT LV",
    "Nordics": "DK FI IS NO SE", "Nordic countries": "DK FI IS NO SE",
    "Pacific Islands": "FJ KI MH FM NR PW PG WS SB TO TV VU",
    "Indian subcontinent": "BD BT IN LK MV NP PK", "Indian Subcontinent": "BD BT IN LK MV NP PK",
    "Central Asia": "KG KZ TJ TM UZ",
}


def iso_names():
    names = {}
    for line in (ZONEINFO / "iso3166.tab").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            code, name = line.split("\t")
            names[code] = name
    return names


def timezones():
    """IANA zone -> country code, from the system zone.tab."""
    zones = {}
    for line in (ZONEINFO / "zone.tab").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            parts = line.split("\t")
            for code in parts[0].split(","):
                zones[parts[2]] = code
    # Names browsers report that older tables list under another name.
    for new, old in {"Europe/Kyiv": "Europe/Kiev", "Asia/Kolkata": "Asia/Calcutta",
                     "America/Nuuk": "America/Godthab", "Asia/Yangon": "Asia/Rangoon"}.items():
        if old in zones:
            zones.setdefault(new, zones[old])
        elif new in zones:
            zones.setdefault(old, zones[new])
    return zones


def clean(text):
    text = re.sub(r"\[\s*[^\]]{1,12}\s*\]", "", text)  # [ 12 ], [ a ], [ citation needed ]
    return re.sub(r"\s+", " ", text).strip(" ,;")


def channels(cell):
    """Split a broadcasters cell into channel names (line breaks, list items, links)."""
    for sup in cell.find_all("sup"):
        sup.decompose()
    for br in cell.find_all("br"):
        br.replace_with("\n")
    for li in cell.find_all("li"):
        li.insert_before("\n")
    parts = []
    for line in cell.get_text("").split("\n"):
        line = clean(line)
        if line and line not in ("–", "-", "—"):
            parts.append(line)
    if len(parts) == 1 and len(cell.find_all("a")) > 1:
        # Several linked channels on one line with no separator.
        links = [clean(a.get_text(" ")) for a in cell.find_all("a")]
        if " ".join(links) == parts[0]:
            parts = links
    return list(dict.fromkeys(parts))


def page_html(page):
    r = requests.get(API, params={"action": "parse", "page": page, "prop": "text|revid", "format": "json",
                                  "formatversion": 2, "redirects": 1}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()["parse"]
    return BeautifulSoup(data["text"], "html.parser"), data["revid"]


def season_ok(heading, season_start):
    """A heading like '2024-27' or '2025–2030' covers the season starting in season_start."""
    years = [int(y) if len(y) == 4 else 2000 + int(y) for y in re.findall(r"\d{4}|(?<=[-–])\d{2}\b", heading)]
    return len(years) >= 2 and years[0] <= season_start < years[-1]


def rights_tables(soup, competition, season_start):
    tables = []
    for t in soup.select("table.wikitable"):
        header = [clean(c.get_text(" ")).lower() for c in t.select("tr")[0].find_all(["th", "td"])]
        if not header or not any(h in ("country", "territory") for h in header[:1]):
            continue
        if not any("broadcast" in h or "rights" in h for h in header):
            continue
        if competition == "Champions League":
            # Men's competition only, and the rights cycle that covers this season.
            section = t.find_previous(lambda tag: tag.name in ("h2", "h3", "h4") and "competition" in tag.get_text())
            cycle = t.find_previous(lambda tag: tag.name in ("h2", "h3", "h4", "h5") and re.search(r"\d{4}", tag.get_text()))
            if not section or "Men" not in section.get_text() or not cycle or not season_ok(cycle.get_text(" "), season_start):
                continue
        tables.append(t)
    return tables


def grid(table):
    """Rows as lists of cells with rowspans filled in, so column 0 is always the country."""
    out, carry = [], {}  # carry: column -> (cell, rows left)
    for tr in table.select("tr")[1:]:
        cells, row, col = tr.find_all(["th", "td"]), [], 0
        while cells or col in carry:
            if col in carry:
                cell, left = carry[col]
                row.append(cell)
                carry[col] = (cell, left - 1)
                if left - 1 == 0:
                    del carry[col]
            else:
                cell = cells.pop(0)
                span = int(re.sub(r"\D", "", cell.get("rowspan", "1")) or 1)
                if span > 1:
                    carry[col] = (cell, span - 1)
                row.append(cell)
            col += 1
        out.append(row)
    return out


def country_names(cell):
    """One cell can list several countries, one per line."""
    for sup in cell.find_all("sup"):
        sup.decompose()
    for br in cell.find_all("br"):
        br.replace_with("\n")
    lines = [clean(x) for x in cell.get_text("").split("\n")]
    return [x for x in lines if x]


def parse_rows(table):
    rows = []
    for row in grid(table):
        if len(row) >= 2:
            chans = channels(BeautifulSoup(str(row[1]), "html.parser"))
            for name in country_names(BeautifulSoup(str(row[0]), "html.parser")):
                rows.append((name, chans))
    return rows


def to_codes(name, by_name):
    if name in REGIONS:
        return REGIONS[name].split()
    for candidate in (name, name.split(" (")[0], name.replace("The ", "")):
        if candidate in ALIASES:
            return [ALIASES[candidate]]
        if candidate in by_name:
            return [by_name[candidate]]
    # "France and Monaco", "Spain and Andorra", "UK and Ireland"
    if " and " in name or " & " in name or "/" in name:
        out = []
        for part in re.split(r" and | & |/|, ", name):
            out += to_codes(part.strip(), by_name)
        return out
    return []


def main(max_age=None):
    if max_age is not None and OUT.exists():
        generated = json.loads(OUT.read_text(encoding="utf-8")).get("generated")
        if generated and (date.today() - date.fromisoformat(generated)).days < max_age:
            print(f"broadcasters.json is from {generated}; skipping")
            return 0
    names = iso_names()
    by_name = {v: k for k, v in names.items()}
    season_start = date.today().year if date.today().month >= 7 else date.today().year - 1

    rights, sources, unmapped = {}, {}, set()
    for comp, page in PAGES.items():
        try:
            soup, revid = page_html(page)
        except requests.RequestException as e:
            print(f"FAILED {comp}: {e}", file=sys.stderr)
            continue
        source = f"https://en.wikipedia.org/w/index.php?title={page.replace(' ', '_')}&oldid={revid}"
        sources[comp] = source
        for table in rights_tables(soup, comp, season_start):
            for country, chans in parse_rows(table):
                codes = to_codes(country, by_name)
                if not codes:
                    unmapped.add(f"{comp}: {country}")
                    continue
                for code in codes:
                    entry = rights.setdefault(comp, {}).setdefault(code, {"channels": [], "source": source})
                    entry["channels"] = list(dict.fromkeys(entry["channels"] + chans))
        print(f"{comp:18} {len(rights.get(comp, {}))} countries")
        time.sleep(2)

    manual = json.loads(MANUAL.read_text(encoding="utf-8")) if MANUAL.exists() else {}
    for comp, countries in manual.get("rights", {}).items():
        for code, entry in countries.items():
            rights.setdefault(comp, {})[code] = entry

    out = {"generated": date.today().isoformat(),
           "_about": "Rights per competition and country. Wikipedia tables plus researched entries "
                     "(data/broadcasters_manual.json). A given match can be on another channel.",
           "sources": sources, "countries": names, "timezones": timezones(),
           "rights": rights, "unmapped": sorted(unmapped)}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{sum(len(v) for v in rights.values())} competition/country entries; {len(unmapped)} names not mapped")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age", type=int)
    sys.exit(main(ap.parse_args().max_age))
