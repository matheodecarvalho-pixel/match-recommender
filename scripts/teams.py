"""One name per club across providers.

A club's key is its teams.csv canonical name when it has a row there; otherwise the
football-data.org short name; otherwise the name ESPN uses. Every name that can't be
tied to teams.csv is logged in `unmatched`, never dropped.
"""
import csv, json

from match_teams import norm

# rivalries.json and records.json use a couple of short forms; build_teams.py folds them the same way.
RENAME = {"Bournemouth": "AFC Bournemouth", "Deportivo": "Deportivo La Coruña"}


class Registry:
    def __init__(self, teams_csv, fd_teams=(), extra_aliases=None):
        self.by_fd, self.by_espn, self.by_tm, self.by_name = {}, {}, {}, {}
        self.unmatched = set()
        for row in csv.DictReader(open(teams_csv, encoding="utf-8")):
            name = row["canonical_name"]
            if row.get("football_data_id"):
                self.by_fd[row["football_data_id"]] = name
            if row.get("espn_id"):
                self.by_espn[row["espn_id"]] = name
            if row.get("transfermarkt_id"):
                self.by_tm[row["transfermarkt_id"]] = name
            for alias in [name] + [a for a in row["aliases"].split("|") if a]:
                self.by_name.setdefault(norm(alias), name)
        # Clubs football-data.org knows but teams.csv doesn't (no rivalry or record):
        # their short name becomes the key, and ESPN names can still match it.
        for t in fd_teams:
            fid = str(t["id"])
            if fid not in self.by_fd:
                self.by_fd[fid] = t.get("short_name") or t["name"]
            for name in (t["name"], t.get("short_name")):
                if name:
                    self.by_name.setdefault(norm(name), self.by_fd[fid])

        for alias, key in (extra_aliases or {}).items():
            if not alias.startswith("_"):
                self.by_name.setdefault(norm(alias), key)

    def canonical(self, name):
        return RENAME.get(name, name)

    def from_fd(self, team):
        fid = str(team["id"])
        if fid in self.by_fd:
            return self.by_fd[fid]
        name = team.get("shortName") or team["name"]
        self.unmatched.add(f"football-data.org: {team['name']} ({fid})")
        return self.by_name.get(norm(team["name"])) or name

    def from_espn(self, espn_id, name):
        if espn_id and espn_id in self.by_espn:
            return self.by_espn[espn_id]
        hit = self.by_name.get(norm(name))
        if hit:
            return hit
        self.unmatched.add(f"ESPN: {name} ({espn_id})")
        return name

    def from_tm(self, tm_id, name):
        """Key for a Transfermarkt club, or None. Callers log what they need to (former clubs
        outside the 7 leagues are expected misses)."""
        if tm_id and tm_id in self.by_tm:
            return self.by_tm[tm_id]
        return self.by_name.get(norm(name)) if name else None


def load(root):
    flat = root / "output" / "raw" / "fd" / "teams_flat.json"
    fd_teams = json.loads(flat.read_text(encoding="utf-8")) if flat.exists() else []
    extra = root / "data" / "extra_aliases.json"
    aliases = json.loads(extra.read_text(encoding="utf-8")) if extra.exists() else {}
    return Registry(root / "data" / "teams.csv", fd_teams, aliases)
