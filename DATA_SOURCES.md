# Data sources (V1, free only)

Status as of 18 Oct 2026. "Verified" = confirmed from the provider's own pages. "To test" = needs a free key to confirm.

## Fixtures, results, tables
| Competitions | Source | Status |
|---|---|---|
| 7 leagues + Champions League | football-data.org free tier (10 calls/min, delayed scores) | Verified |
| Europa League, Conference League | ESPN public JSON feed (site.api.espn.com scoreboard + standings), via scrape_europe.py | Working since 18 Oct 2026. Unofficial and undocumented: no key, could change without notice. Football Web Pages (the first choice) returns a Cloudflare bot check (403) and was dropped, not worked around |

Why not Google: Google doesn't publish this data openly, blocks automated queries, and sued a scraping company (SerpApi) in Dec 2025. Why not Wikipedia: on 18 Oct 2026 its Conference League page still showed no Matchday 1 scores from 15 Oct.

## Record tracking
| Need | Source | Notes |
|---|---|---|
| Team streaks (unbeaten, wins), points/goals pace | Computed from results (football-data.org) | Free, no extra data |
| Player season goals | football-data.org `scorers` endpoint | Free for the 12 free competitions |
| Player scoring streaks | Diff the `scorers` list after each matchday: if a player's goal total rose after his team played, he scored | Free. Only covers players in the returned top-scorer list, which is where record chasers are anyway |
| Player scoring streaks (alternative) | API-Football `fixtures/events` (goalscorers per match) | Free tier lists Events; ~120 fixtures/week in European weeks, within 100 calls/day if one call per fixture spread over the week |
| Goalkeeper clean sheets | API-Football `fixtures/lineups` + result | football-data.org lineups start at the €29 plan, so this depends on API-Football's free tier |
| Record values | records.json (Wikipedia, UEFA, bundesliga.com, The Analyst) | Refresh at season start; Ligue 1 and part of Serie A flagged to verify |

## Revenge games
Transfermarkt, scraped twice a season (after each transfer window closes). No official API; slow requests, cache results. Check Transfermarkt's terms before a public launch.

`scripts/scrape_transfermarkt.py` reads two pages per club in the 7 leagues: the detailed squad (`/kader/.../plus/1`, "Joined" and "Signed from" columns) and the staff page (`/mitarbeiter/...`, the manager's appointment date and previous club). robots.txt allows them. 4 s between requests, pages cached in `output/transfermarkt/cache/` (not committed), about 20 minutes for a full run. A 403/429 or bot-check page stops the run. Output: `output/transfermarkt/squads_YYYY-MM-DD.json` (build.py uses the newest) and `clubs.json` for `match_teams.py`. Run it from the manual "Transfermarkt squads" workflow.

A match is flagged when someone joined from the opponent within `signals.revenge.transfer_window_months`. Clubs are compared by Transfermarkt id, so moves from a U21 side don't count. Players currently on loan from the opponent are skipped (`include_current_loans`, false by default) because many leagues bar loanees from facing their parent club. The manager's "previous club" is the last club on his staff record, which can be an assistant job (Arteta: Manchester City).

## Team names
teams.csv holds one canonical name per club. Run match_teams.py once per provider to fill football_data_id, api_football_id and transfermarkt_id; fix any "no match" lines by hand.

## Not tracked (no free source)
Clean sheets, minutes without conceding, fewest goals conceded, career totals and titles. Those records never score.

## Club revenge and European classics
| Need | Source | Notes |
|---|---|---|
| Last season's Champions League (knockouts included) | football-data.org `competitions/CL/matches?season=<last>` | Fetched once into output/history/ (free tier allows the previous season) |
| Last 13 months of Europa/Conference League | ESPN scoreboard, one request per month (`dates=YYYYMM`), with round (`season.slug`) and winner flags | Cached in output/europe_history/; a finished month is never refetched |
| European meetings since 2020 per pair | football-data.org `matches/{id}/head2head` for upcoming Champions League fixtures | Cached in output/h2h_cache.json, refetched only after the pair meets again. Free history starts around 2020. Europa/Conference fixtures can't use it (not in the free tier), so classics are only detected for Champions League matches |
