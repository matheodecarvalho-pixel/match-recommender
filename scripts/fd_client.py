"""football-data.org v4 client with a client-side throttle (free tier: 10 requests/min).

The token comes from the FOOTBALL_DATA_TOKEN environment variable, or from a
.env file at the repo root (never committed).
"""
import os, time
from pathlib import Path

import requests

BASE = "https://api.football-data.org/v4"
ROOT = Path(__file__).resolve().parent.parent

# The 8 competitions football-data.org covers for us, code -> display name.
COMPETITIONS = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "DED": "Eredivisie",
    "PPL": "Primeira Liga",
    "CL": "Champions League",
}

MIN_INTERVAL = 6.5  # seconds between calls: stays under 10/min with a margin


def load_token():
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if token:
        return token.strip()
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "FOOTBALL_DATA_TOKEN" and value.strip():
                return value.strip()
    raise SystemExit("FOOTBALL_DATA_TOKEN is not set (env var or .env file)")


class Client:
    def __init__(self, token=None):
        self.session = requests.Session()
        self.session.headers.update({
            "X-Auth-Token": token or load_token(),
            "User-Agent": "personal-match-recommender/0.1 (personal use, 1 run/day)",
        })
        self._last = 0.0

    def get(self, path, **params):
        for attempt in range(3):
            wait = MIN_INTERVAL - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            r = self.session.get(f"{BASE}{path}", params=params or None, timeout=30)
            if r.status_code == 429:
                # The server says how long to wait in the message; a full minute is always safe.
                time.sleep(61)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()
