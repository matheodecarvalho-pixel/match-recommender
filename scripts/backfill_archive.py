"""One-off: rebuild output/score_archive.json from every matches_ranked.json in git history.

Each commit is a snapshot of the scores shown that day. Going oldest to newest, a match's
entry is overwritten until the snapshot is taken after its kickoff, so the archive ends up
with the last score published before each match started.

  python scripts/backfill_archive.py
"""
import json, subprocess
from datetime import datetime

from build import ARCHIVE, frozen
from fd_client import ROOT

FILE = "output/matches_ranked.json"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def main():
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else {}
    commits = git("log", "--reverse", "--format=%H", "--", FILE).split()
    snapshots = 0
    for sha in commits:
        try:
            data = json.loads(git("show", f"{sha}:{FILE}"))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        taken = datetime.fromisoformat(data["generated_at"])
        snapshots += 1
        for m in data["matches"]:
            if datetime.fromisoformat(m["kickoff_paris"]) > taken:
                archive[m["id"]] = {**frozen(m), "frozen_at": data["generated_at"]}
    ARCHIVE.write_text(json.dumps(archive, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(f"{snapshots} snapshots read, {len(archive)} matches in the archive")


if __name__ == "__main__":
    main()
