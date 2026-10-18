"""Squads and managers of the 7 league clubs, with each person's previous club and join date.

Source: transfermarkt.com HTML (no official API; robots.txt allows these pages). Per club,
two pages: the detailed squad (/kader/.../plus/1: "Joined" and "Signed from" columns) and the
staff page (/mitarbeiter/...: the manager's appointment date and previous club).

Runs twice a season, after each transfer window closes (manual GitHub workflow), not daily.
Every page is cached as HTML in output/transfermarkt/cache/ and reused while it is younger
than --max-age-days, so a re-run (or a resumed run) fetches nothing it already has.
Requests are 4 seconds apart. A bot check (Cloudflare, captcha, 403/429) stops the run:
it is reported, never worked around.

  python scripts/scrape_transfermarkt.py                 # all 7 leagues, current season
  python scripts/scrape_transfermarkt.py --leagues GB1   # one league
  python scripts/scrape_transfermarkt.py --debug 11      # parse one club (Transfermarkt id), print it

Output:
  output/transfermarkt/squads_YYYY-MM-DD.json   snapshot (build.py reads the newest)
  output/transfermarkt/clubs.json               id/name/country list for match_teams.py
"""
import argparse, json, re, sys, time
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from fd_client import ROOT

BASE = "https://www.transfermarkt.com"
LEAGUES = {
    "GB1": ("Premier League", "England"),
    "ES1": ("La Liga", "Spain"),
    "IT1": ("Serie A", "Italy"),
    "L1": ("Bundesliga", "Germany"),
    "FR1": ("Ligue 1", "France"),
    "NL1": ("Eredivisie", "Netherlands"),
    "PO1": ("Primeira Liga", "Portugal"),
}
HEADERS = {"User-Agent": "personal-match-recommender/0.1 (personal use, runs twice a season)",
           "Accept-Language": "en"}
DELAY_SECONDS = 4
RETRIES, RETRY_WAIT_SECONDS = 2, 30
OUT = ROOT / "output" / "transfermarkt"
CACHE = OUT / "cache"
MANAGER_ROLES = ("manager", "head coach", "caretaker manager", "interim manager")
CLUB_HREF = re.compile(r"/verein/(\d+)")
PERSON_HREF = re.compile(r"/(?:spieler|trainer)/(\d+)")


class Blocked(Exception):
    pass


def check_blocked(status, html):
    head = html[:5000].lower()
    if status in (403, 429, 503) or "cf-chl" in head or "just a moment" in head or "captcha" in head:
        raise Blocked(f"HTTP {status}, bot check or rate limit")


class Fetcher:
    def __init__(self, max_age_days):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.max_age = max_age_days * 86400
        self._last = 0.0
        self.fetched = 0

    def get(self, path, key):
        cached = CACHE / f"{key}.html"
        if cached.exists() and time.time() - cached.stat().st_mtime < self.max_age:
            return cached.read_text(encoding="utf-8")
        for attempt in range(RETRIES + 1):
            wait = DELAY_SECONDS - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            # A slow connection or a server error is not a refusal: back off and try again.
            try:
                r = self.session.get(BASE + path, timeout=30)
                if r.status_code not in (500, 502, 504) or attempt == RETRIES:
                    break
            except (requests.Timeout, requests.ConnectionError):
                if attempt == RETRIES:
                    raise
            time.sleep(RETRY_WAIT_SECONDS)
        self.fetched += 1
        check_blocked(r.status_code, r.text)
        r.raise_for_status()
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(r.text, encoding="utf-8")
        return r.text


def tm_date(text):
    """'04/07/2024' -> '2024-07-04'; anything else (e.g. '-') -> None."""
    try:
        return datetime.strptime(text.strip(), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def club_link(a):
    m = CLUB_HREF.search(a.get("href", "")) if a else None
    if not m:
        return None, None
    name = (a.img.get("alt") if a.img else None) or a.get("title", "").split(":")[0]
    return m.group(1), name.strip() or None


def parse_league(html):
    """Club ids and names from a league overview page."""
    soup = BeautifulSoup(html, "html.parser")
    clubs = {}
    for a in soup.select("table.items td.hauptlink a[href*='/startseite/verein/']"):
        cid, _ = club_link(a)
        clubs.setdefault(cid, a.get("title") or a.get_text(strip=True))
    return clubs


def parse_squad(html):
    """Players from the detailed squad page (/plus/1)."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.items")
    if table is None:
        return []
    heads = [th.get_text(" ", strip=True) for th in table.select("thead th")]
    try:
        i_joined, i_from = heads.index("Joined"), heads.index("Signed from")
    except ValueError:
        return []
    people = []
    for tr in table.select("tbody > tr"):
        cells = tr.find_all("td", recursive=False)
        link = tr.select_one("td.hauptlink a[href*='/profil/spieler/']")
        if not link or len(cells) < len(heads):
            continue
        # Header and body columns line up one to one; the name cell holds a nested table.
        joined, signed = cells[i_joined], cells[i_from]
        a = signed.find("a")
        from_id, from_name = club_link(a)
        # A current loanee's row carries "On loan from X until ..."; "Signed from" is then X.
        # Players back from a loan keep their original club in "Signed from".
        on_loan = any(t.get("title", "").startswith("On loan from") for t in tr.select("[title]"))
        people.append({"name": link.get_text(" ", strip=True), "tm_id": PERSON_HREF.search(link["href"]).group(1),
                       "role": "player", "joined": tm_date(joined.get_text()),
                       "from_tm_id": from_id, "from_name": from_name, "transfer": "loan" if on_loan else "transfer"})
    return people


def parse_staff(html):
    """The manager from the staff page: appointment date and previous club."""
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.select("a[href*='/profil/trainer/']"):
        inline = link.find_parent("table", class_="inline-table")
        row = inline.find_parent("tr") if inline else None
        role_rows = inline.find_all("tr") if inline else []
        role = role_rows[1].get_text(" ", strip=True).lower() if len(role_rows) > 1 else ""
        if not row or role not in MANAGER_ROLES:
            continue
        cells = row.find_all("td", recursive=False)
        if len(cells) < 6:
            continue
        from_id, from_name = club_link(cells[5].find("a"))
        return [{"name": link.get_text(" ", strip=True), "tm_id": PERSON_HREF.search(link["href"]).group(1),
                 "role": "manager", "joined": tm_date(cells[3].get_text()),
                 "from_tm_id": from_id, "from_name": from_name, "transfer": "transfer"}]
    return []


def season_id(today):
    """Transfermarkt names a season by its starting year (2026 = 2026/27)."""
    return today.year if today.month >= 7 else today.year - 1


def club_people(fetcher, cid, season):
    squad = fetcher.get(f"/x/kader/verein/{cid}/saison_id/{season}/plus/1", f"squad_{cid}_{season}")
    staff = fetcher.get(f"/x/mitarbeiter/verein/{cid}", f"staff_{cid}")
    return parse_squad(squad) + parse_staff(staff)


def run(leagues, max_age_days):
    fetcher = Fetcher(max_age_days)
    today = date.today()
    season = season_id(today)
    clubs, warnings = [], []
    try:
        for code in leagues:
            competition, country = LEAGUES[code]
            html = fetcher.get(f"/x/startseite/wettbewerb/{code}/saison_id/{season}", f"league_{code}_{season}")
            found = parse_league(html)
            if not found:
                warnings.append(f"{competition}: no clubs parsed from the league page")
            for cid, name in found.items():
                try:
                    people = club_people(fetcher, cid, season)
                except requests.RequestException as e:
                    warnings.append(f"{name} ({cid}): skipped, request failed ({e})")
                    continue
                if not any(p["role"] == "player" for p in people):
                    warnings.append(f"{name} ({cid}): no players parsed")
                if not any(p["role"] == "manager" for p in people):
                    warnings.append(f"{name} ({cid}): no manager found")
                clubs.append({"tm_id": cid, "name": name, "competition": competition,
                              "country": country, "people": people})
                print(f"{competition}: {name} ({len(people)} people)", file=sys.stderr)
    except Blocked as e:
        print(f"STOPPED: Transfermarkt blocked the request ({e}). Not working around it; "
              f"{len(clubs)} clubs parsed, nothing written.", file=sys.stderr)
        sys.exit(2)

    snapshot = {"fetched_at": datetime.now().astimezone().isoformat(), "season": season,
                "source": "transfermarkt.com squad and staff pages", "clubs": clubs, "warnings": warnings}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"squads_{today.isoformat()}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")

    # Provider list for match_teams.py: league clubs (with country) plus every former club seen.
    provider = {c["tm_id"]: {"id": c["tm_id"], "name": c["name"], "country": c["country"]} for c in clubs}
    for c in clubs:
        for p in c["people"]:
            if p["from_tm_id"] and p["from_name"]:
                provider.setdefault(p["from_tm_id"], {"id": p["from_tm_id"], "name": p["from_name"], "country": None})
    (OUT / "clubs.json").write_text(json.dumps(list(provider.values()), ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    print(f"{len(clubs)} clubs, {sum(len(c['people']) for c in clubs)} people -> {path.relative_to(ROOT)} "
          f"({fetcher.fetched} pages fetched, rest from cache)")
    for w in warnings:
        print("WARNING:", w, file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", default=list(LEAGUES), choices=list(LEAGUES))
    ap.add_argument("--max-age-days", type=float, default=7, help="reuse cached pages younger than this")
    ap.add_argument("--debug", metavar="CLUB_ID", help="parse one club and print it")
    a = ap.parse_args()
    if a.debug:
        print(json.dumps(club_people(Fetcher(a.max_age_days), a.debug, season_id(date.today())),
                         ensure_ascii=False, indent=1))
    else:
        run(a.leagues, a.max_age_days)
