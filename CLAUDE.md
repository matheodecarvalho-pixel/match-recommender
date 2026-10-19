# Eyeball: build brief

A personal website that answers one question: **which football matches are worth watching this week, and why?**
It ranks every match from the competitions below with a 0-100 "watchability" score and shows the reasons in one line.

Owner: Matheo. Personal use only. **Everything must stay free** (no paid APIs, no paid hosting).

## V1 scope

Competitions:
- Leagues: Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira Liga
- Europe: Champions League, Europa League, Conference League

Signals (see `config/scoring.json` for every number):
form, stakes, entertainment, rivalry, closeness, records, revenge games, plus favourite teams and a must-watch override.

**Out of scope for V1:** domestic cups (V2), user accounts, notifications, paid data.

## Stack

- **Data pipeline:** Python 3.11+. Scripts in `scripts/`, output JSON in `output/`.
- **Website:** static site in `site/` (plain HTML, CSS, vanilla JS; no build step). Reads `output/matches_ranked.json`.
- **Schedule:** GitHub Actions, once a day (around 06:00 Paris). Commits fresh JSON; site served by GitHub Pages.
- **Secrets:** `FOOTBALL_DATA_TOKEN` (free key from football-data.org) as an environment variable / repo secret. Never commit it.

## Repo layout

```
CLAUDE.md               this brief
DATA_SOURCES.md         where every piece of data comes from, and what is verified
config/scoring.json     weights, thresholds, story templates (all tunable)
data/rivalries.json     209 rivalries, tier 1-3, with source per row
data/records.json       70 records (holder, value, metric to track, source)
data/teams.csv          201 clubs: canonical name, aliases, provider ID columns
scripts/match_teams.py  fills provider IDs in teams.csv from a provider team list
scripts/scrape_europe.py  daily Europa + Conference League fixtures/results
scripts/build_teams.py  regenerates teams.csv from the data files
scripts/scrape_transfermarkt.py  squads + managers with previous club (twice a season)
scripts/revenge.py      revenge flags from the newest Transfermarkt snapshot
brand/                  logo files (SVG/PNG) and BRAND.md: colours, fonts, usage
output/                 generated JSON (pipeline writes here)
site/                   the website
```

## Data sources (details in DATA_SOURCES.md)

| Data | Source | Cadence |
|---|---|---|
| 7 leagues + Champions League: fixtures, results, standings, top scorers | football-data.org v4, free tier (10 requests/min, delayed scores) | Daily |
| Europa League + Conference League: fixtures, results, league-phase table | ESPN public JSON feed via `scripts/scrape_europe.py` (Football Web Pages is behind Cloudflare) | Daily |
| Revenge games: player and manager moves | Transfermarkt, scraped (no official API) | Twice a season, after each transfer window closes |
| Rivalries | `data/rivalries.json` | Static |
| Records | `data/records.json` | Refresh at season start |

Rules for scraping: identify the client in the User-Agent, wait at least 4 seconds between requests, cache everything, never re-fetch what hasn't changed. Respect football-data.org's 10 requests/min limit with a client-side throttle.

## Pipeline (daily run)

1. **Fetch** fixtures/results/standings/scorers for the 8 football-data.org competitions; run `scrape_europe.py` for Europa/Conference League.
2. **Normalise team names** to `data/teams.csv` canonical names (match by provider ID, else by alias). Log any unmatched name; never silently drop a match.
3. **Compute per-team stats:** last-N form (points per game), goals for/against, table position, points gaps, current win and unbeaten streaks.
4. **Track records:**
   - Team records (streaks, points/goals pace): compute from results.
   - Player season goals: from football-data.org `scorers`.
   - Player scoring streaks: compare today's `scorers` snapshot with the previous one (keep snapshots in `output/scorers_history/`). If a player's goal total rose after his team played, his streak continues; if his team played and it didn't rise, it resets.
   - Show **distance** to the record, never a prediction ("2 goals from the record", "needs to score in 2 more games").
5. **Revenge flags:** from the latest Transfermarkt snapshot, flag a match if a player or manager in one squad joined from the opponent within `transfer_window_months`.
6. **Score** every match in the next 7 days with `config/scoring.json`: each signal 0-1, weighted to 0-100, plus competition bonus and favourite boost, capped at 100.
7. **Must-watch:** score ≥ threshold or tier-1 rivalry. Must-watch matches always rank above favourite-team matches.
8. **Story line:** top `max_reasons` contributing signals, using the templates. Every reason must come from real data; if a value is missing, drop that reason rather than invent one.
9. **Write** `output/matches_ranked.json` (one object per match: competition, kickoff in Europe/Paris, teams, score, must_watch, story, and the per-signal breakdown).

## Website (V1)

- One page: this week's matches, ranked by score, grouped by day.
- Each card: kickoff (Paris time), competition, teams, score, must-watch badge, story line.
- Tap a card to see the score breakdown per signal (transparency is a core feature).
- Filter by competition. Favourite teams picker, saved in `localStorage` (wrap in try/catch).
- Works well on a phone.
- Use the identity in `brand/BRAND.md`: night background, chalk text, emerald accent, Bricolage Grotesque + Instrument Sans, `brand/logo.svg` in the header, `brand/favicon.svg` as favicon.

## Build order

1. football-data.org client + throttle; fetch the 8 competitions; save raw JSON.
2. Run `scripts/match_teams.py` against each provider's team list; fix unmatched names in `data/teams.csv`.
3. Run `scripts/scrape_europe.py` once; if it finds 0 matches, use its `--debug` mode and fix the parser.
4. Stats + scoring engine + story lines, with unit tests on hand-made fixtures.
5. Record tracking (team records first, then the scorers-diff streaks).
6. Static site.
7. GitHub Actions daily job + GitHub Pages.
8. Transfermarkt scraper + revenge flags (last, since it runs twice a season).

## Known caveats (check before trusting output)

- `scrape_europe.py` and `match_teams.py` were tested only on sample data; their first real run is the true test.
- `data/records.json`: rows with a `note` flagged "verify" (all Ligue 1, 4 Serie A, Neuer's Bundesliga clean sheets) need checking against the live source. Serie A, Eredivisie and Primeira Liga are missing team records.
- ESPN kickoff times are UTC: convert with `zoneinfo` to Europe/Paris, never by adding a fixed hour. The ESPN feed is unofficial and may change.
- Transfermarkt has no official API and its terms on scraping weren't confirmed: fine for personal use, re-check before any public launch.

## Working rules

- Free only. If a feature needs paid data, stop and say so instead of adding it.
- Never invent data. Missing data means the signal scores 0 and the story skips it.
- Keep every tunable number in `config/scoring.json`, not in code.
- Small commits, one step of the build order at a time.
