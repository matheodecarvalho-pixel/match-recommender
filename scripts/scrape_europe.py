"""Daily scraper for Europa League and Conference League (Champions League optional).

Source: Football Web Pages date pages, e.g.
  https://www.footballwebpages.co.uk/uefa-europa-league/20261022
Each page lists that day's matches: kickoff time (UK time) before the game,
final score after it.

Run once a day (personal use). It checks a window of dates, sleeps between
requests, and writes europe_matches.json.

  pip install requests beautifulsoup4
  python scrape_europe.py                 # default window: 3 days back, 10 ahead
  python scrape_europe.py --debug 20261022 uefa-europa-league
"""
import argparse, json, re, sys, time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://www.footballwebpages.co.uk"
COMPETITIONS = {
    "uefa-europa-league": "Europa League",
    "uefa-conference-league": "Conference League",
    # "uefa-champions-league": "Champions League",  # already covered by football-data.org
}
UK, PARIS = ZoneInfo("Europe/London"), ZoneInfo("Europe/Paris")
HEADERS = {"User-Agent": "personal-match-recommender/0.1 (personal use, 1 run/day)"}
DELAY_SECONDS = 4

SCORE = re.compile(r"^(\d+)\s*[-–]\s*(\d+)$")
TIME = re.compile(r"^(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)$", re.I)


def kickoff_iso(day, text):
    m = TIME.match(text)
    h, mins, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
    if ampm == "pm" and h != 12:
        h += 12
    if ampm == "am" and h == 12:
        h = 0
    uk = datetime(day.year, day.month, day.day, h, mins, tzinfo=UK)
    return uk.astimezone(PARIS).isoformat()


def parse(html, day, competition):
    """Find rows shaped like: home | score-or-time | away.

    Written against the page's visible layout (home, middle cell, away), not its
    exact markup, so it survives cosmetic changes. If the site changes layout,
    this returns [] and the run logs a warning.
    """
    soup = BeautifulSoup(html, "html.parser")
    matches = []
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c and c.lower() not in {"v", "vs", "ft", "aet", "pens"}]
        for i in range(1, len(cells) - 1):
            mid = cells[i]
            s, t = SCORE.match(mid), TIME.match(mid)
            if not (s or t):
                continue
            home, away = cells[i - 1], cells[i + 1]
            if SCORE.match(home) or TIME.match(home) or SCORE.match(away) or TIME.match(away):
                continue
            row = {"competition": competition, "date": day.isoformat(),
                   "home": home, "away": away, "status": "finished" if s else "scheduled"}
            if s:
                row["home_goals"], row["away_goals"] = int(s.group(1)), int(s.group(2))
            else:
                row["kickoff_paris"] = kickoff_iso(day, mid)
            matches.append(row)
            break
    return matches


def fetch(slug, day, session):
    url = f"{BASE}/{slug}/{day:%Y%m%d}"
    r = session.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def run(back=3, ahead=10, out="output/europe_matches.json"):
    session = requests.Session()
    today = date.today()
    found, warnings = [], []
    for slug, name in COMPETITIONS.items():
        for offset in range(-back, ahead + 1):
            day = today + timedelta(days=offset)
            try:
                rows = parse(fetch(slug, day, session), day, name)
            except requests.RequestException as e:
                warnings.append(f"{name} {day}: request failed ({e})")
                rows = []
            # UEFA club matches are played on Tuesdays-Thursdays. Zero rows on a
            # Thursday is suspicious (layout change or blocked request).
            if not rows and day.weekday() == 3:
                warnings.append(f"{name} {day}: 0 matches on a Thursday, check the parser")
            found.extend(rows)
            time.sleep(DELAY_SECONDS)

    # Keep one row per fixture (same match can't appear twice, but be safe).
    unique = {(m["competition"], m["date"], m["home"], m["away"]): m for m in found}
    data = {"scraped_at": datetime.now(PARIS).isoformat(), "source": BASE,
            "matches": sorted(unique.values(), key=lambda m: (m["date"], m["competition"], m["home"])),
            "warnings": warnings}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"{len(data['matches'])} matches saved to {out}")
    for w in warnings:
        print("WARNING:", w, file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", nargs=2, metavar=("YYYYMMDD", "SLUG"),
                    help="fetch one page, print parsed rows, save raw HTML to debug.html")
    ap.add_argument("--back", type=int, default=3)
    ap.add_argument("--ahead", type=int, default=10)
    a = ap.parse_args()
    if a.debug:
        d = datetime.strptime(a.debug[0], "%Y%m%d").date()
        html = fetch(a.debug[1], d, requests.Session())
        open("debug.html", "w", encoding="utf-8").write(html)
        print(json.dumps(parse(html, d, a.debug[1]), ensure_ascii=False, indent=1))
    else:
        run(a.back, a.ahead)
