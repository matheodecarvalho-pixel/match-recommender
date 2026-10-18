# Match Recommender

Which football matches are worth watching this week, and why.

## Start
1. Get a free API key at football-data.org and set it: `export FOOTBALL_DATA_TOKEN=...`
2. `pip install requests beautifulsoup4`
3. Run the pipeline:
   ```
   python scripts/fetch_fd.py --teams && python scripts/fd_teams_flat.py
   python scripts/scrape_europe.py
   python scripts/build.py
   ```
4. View the site: `python3 -m http.server` in this folder, then open http://localhost:8000/site/
5. Tests: `python -m pytest tests`

Tune the ranking any time in `config/scoring.json`.
