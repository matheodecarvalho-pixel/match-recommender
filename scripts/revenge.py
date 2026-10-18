"""Revenge flags: someone in one squad joined from the opponent within the configured window.

Reads the newest Transfermarkt snapshot (output/transfermarkt/squads_*.json, written by
scrape_transfermarkt.py). Clubs are compared by Transfermarkt id, so a player signed from
a club's U21 side never counts as coming from the first team.
"""
import json
from datetime import date


def load_snapshot(folder):
    paths = sorted(folder.glob("squads_*.json"))
    return json.loads(paths[-1].read_text(encoding="utf-8")) if paths else None


def months_before(day, months):
    y, m = divmod(day.year * 12 + day.month - 1 - months, 12)
    m += 1
    for d in (day.day, 30, 29, 28):  # clamp 31 March - 1 month to 28/29 February
        try:
            return date(y, m, d)
        except ValueError:
            continue


class Revenge:
    def __init__(self, snapshot, registry, cfg, warnings=None):
        self.cfg = cfg
        self.squads = {}
        # Opponent ids: teams.csv first (covers clubs outside the 7 leagues), then the snapshot.
        self.tm_ids = {key: tm for tm, key in registry.by_tm.items()}
        for club in (snapshot or {}).get("clubs", []):
            key = registry.from_tm(club["tm_id"], club["name"])
            if key is None:
                if warnings is not None:
                    warnings.append(f"Transfermarkt: {club['name']} ({club['tm_id']}) not matched to a team")
                continue
            self.squads[key] = club["people"]
            self.tm_ids.setdefault(key, club["tm_id"])

    def flags(self, home, away, kickoff):
        """[{'person', 'role', 'team', 'from', 'joined'}] for one match; kickoff is a datetime."""
        since = months_before(kickoff.date(), self.cfg["transfer_window_months"])
        out = []
        for team, opponent in ((home, away), (away, home)):
            opp_id = self.tm_ids.get(opponent)
            if not opp_id:
                continue
            for p in self.squads.get(team, []):
                if p["from_tm_id"] != opp_id or not p["joined"]:
                    continue
                # Loanees are often barred from facing their parent club, so they don't count by default.
                if p["transfer"] == "loan" and not self.cfg["include_current_loans"]:
                    continue
                if since <= date.fromisoformat(p["joined"]) <= kickoff.date():
                    out.append({"person": p["name"], "role": p["role"], "team": team,
                                "from": opponent, "joined": p["joined"]})
        return out
