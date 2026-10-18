# Data sources (V1, free only)

Status as of 18 Oct 2026. "Verified" = confirmed from the provider's own pages. "To test" = needs a free key to confirm.

## Fixtures, results, tables
| Competitions | Source | Status |
|---|---|---|
| 7 leagues + Champions League | football-data.org free tier (10 calls/min, delayed scores) | Verified |
| Europa League, Conference League | Football Web Pages date pages, scraped once a day (scrape_europe.py) | Verified: date pages show fixtures with UK kickoff times and final scores, e.g. /uefa-europa-league/20261022 |

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

## Team names
teams.csv holds one canonical name per club. Run match_teams.py once per provider to fill football_data_id, api_football_id and transfermarkt_id; fix any "no match" lines by hand.
