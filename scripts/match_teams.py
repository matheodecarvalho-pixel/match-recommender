"""Fill provider IDs in teams.csv by matching a provider's real team list.

Usage:
  python match_teams.py teams.csv provider_teams.json football_data_id
  python match_teams.py teams.csv provider_teams.json api_football_id
  python match_teams.py teams.csv provider_teams.json transfermarkt_id

provider_teams.json is a list of {"id": ..., "name": ..., "country": ...}
saved from the provider (for football-data.org: /v4/competitions/{code}/teams;
flatten "teams" into that shape). Anything unmatched or ambiguous is printed
so a human can fix it once in teams.csv.
"""
import csv, json, re, sys, unicodedata

NOISE = {"fc", "cf", "afc", "ac", "as", "sc", "ss", "ssc", "us", "rc", "rcd", "cd", "ud",
         "sd", "ca", "bv", "sv", "vfl", "vfb", "tsg", "fk", "sl", "sco", "ogc", "osc",
         "club", "de", "calcio", "1909", "1913", "1907", "1901", "1848", "1910", "04", "09"}

def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    words = [w for w in re.split(r"[^a-z0-9]+", s) if w and w not in NOISE]
    return " ".join(words)

def keys(row):
    names = [row["canonical_name"]] + [a for a in row["aliases"].split("|") if a]
    return {norm(n) for n in names if norm(n)}

def main(teams_path, provider_path, column):
    rows = list(csv.DictReader(open(teams_path, encoding="utf-8")))
    provider = json.load(open(provider_path, encoding="utf-8"))
    index = {}
    for p in provider:
        index.setdefault(norm(p["name"]), []).append(p)

    matched, unmatched, ambiguous = 0, [], []
    for row in rows:
        if row[column]:
            matched += 1
            continue
        hits = {p["id"]: p for k in keys(row) for p in index.get(k, [])}
        if row.get("country"):
            same = {i: p for i, p in hits.items()
                    if not p.get("country") or p["country"] == row["country"]}
            hits = same or hits
        if len(hits) == 1:
            row[column] = str(next(iter(hits)))
            matched += 1
        elif not hits:
            unmatched.append(row["canonical_name"])
        else:
            ambiguous.append((row["canonical_name"], [p["name"] for p in hits.values()]))

    with open(teams_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

    print(f"{matched}/{len(rows)} matched for {column}")
    for n in unmatched:
        print("  no match:", n)
    for n, opts in ambiguous:
        print("  ambiguous:", n, "->", opts)

if __name__ == "__main__":
    main(*sys.argv[1:4])
