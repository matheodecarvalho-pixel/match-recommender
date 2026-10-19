from datetime import date, datetime, timezone

import pytest

from revenge import Revenge, months_before
from score import signal_revenge
from scrape_transfermarkt import Blocked, check_blocked, parse_league, parse_squad, parse_staff
from teams import Registry

KICKOFF = datetime(2026, 10, 25, 18, tzinfo=timezone.utc)

# --- scraper parsing (trimmed copies of real Transfermarkt markup) ---

SQUAD = """<table class="items"><thead><tr><th>#</th><th>Player</th><th>Date of birth/Age</th><th>Nat.</th>
<th>Height</th><th>Foot</th><th>Joined</th><th>Signed from</th><th>Contract</th><th>Market value</th></tr></thead>
<tbody>
<tr class="odd"><td>1</td><td class="posrela"><table class="inline-table"><tr><td rowspan="2"><img/></td>
<td class="hauptlink"><a href="/david-raya/profil/spieler/262749"> David Raya </a></td></tr><tr><td>Goalkeeper</td></tr></table></td>
<td>15/09/1995 (31)</td><td></td><td>1,86m</td><td>right</td><td class="zentriert">04/07/2024</td>
<td><a href="/fc-brentford/startseite/verein/1148/saison_id/2024" title="Brentford FC: Ablöse €31.90m"><img alt="Brentford FC"/></a></td>
<td>30/06/2028</td><td>€30.00m</td></tr>
<tr class="even"><td>9</td><td class="posrela"><a href="/x/startseite/verein/5" title="On loan from AC Milan until 30/06/2027"><img/></a><table class="inline-table"><tr><td rowspan="2"><img/></td>
<td class="hauptlink"><a href="/some-one/profil/spieler/1"> Some One </a></td></tr><tr><td>Centre-Forward</td></tr></table></td>
<td>01/01/2000 (26)</td><td></td><td>1,80m</td><td>left</td><td class="zentriert">01/09/2026</td>
<td><a href="/x/startseite/verein/5/saison_id/2026" title="AC Milan: Ablöse ?"><img alt="AC Milan"/></a></td>
<td>30/06/2027</td><td>€5.00m</td></tr>
<tr class="odd"><td>40</td><td class="posrela"><table class="inline-table"><tr><td rowspan="2"><img/></td>
<td class="hauptlink"><a href="/kid/profil/spieler/2"> Kid </a></td></tr><tr><td>Winger</td></tr></table></td>
<td>01/01/2008 (18)</td><td></td><td>1,70m</td><td>left</td><td class="zentriert">-</td>
<td><a href="/x/startseite/verein/1234/saison_id/2026" title="Arsenal FC U21: Ablöse -"><img alt="Arsenal FC U21"/></a></td>
<td>-</td><td>-</td></tr>
</tbody></table>"""

STAFF = """<table><tbody>
<tr><td><table class="inline-table"><tr><td rowspan="2"><img/></td>
<td class="hauptlink"><a href="/mikel-arteta/profil/trainer/47620" title="Mikel Arteta">Mikel Arteta</a></td></tr>
<tr><td>Manager</td></tr></table></td><td>44</td><td></td><td class="zentriert">22/12/2019</td><td>30.06.2030</td>
<td><a href="/manchester-city/startseite/verein/281/saison_id/2019" title="Manchester City"><img alt="Manchester City"/></a></td></tr>
<tr><td><table class="inline-table"><tr><td rowspan="2"><img/></td>
<td class="hauptlink"><a href="/assistant/profil/trainer/4084" title="Assistant">Assistant</a></td></tr>
<tr><td>Assistant Manager</td></tr></table></td><td>56</td><td></td><td>24/12/2019</td><td>-</td>
<td><a href="/wales/startseite/verein/3864/saison_id/2022" title="Wales"><img alt="Wales"/></a></td></tr>
</tbody></table>"""

LEAGUE = """<table class="items"><tbody><tr><td class="hauptlink"><a title="Arsenal FC" href="/fc-arsenal/startseite/verein/11/saison_id/2026">Arsenal</a></td></tr>
<tr><td class="hauptlink"><a title="Chelsea FC" href="/fc-chelsea/startseite/verein/631/saison_id/2026">Chelsea</a></td></tr></tbody></table>"""


def test_parse_squad_reads_join_date_previous_club_and_loans():
    raya, loanee, kid = parse_squad(SQUAD)
    assert raya == {"name": "David Raya", "tm_id": "262749", "role": "player", "joined": "2024-07-04",
                    "from_tm_id": "1148", "from_name": "Brentford FC", "transfer": "transfer"}
    assert loanee["transfer"] == "loan" and loanee["from_tm_id"] == "5"
    assert kid["joined"] is None  # "-" is missing data, not a date


def test_parse_staff_picks_the_manager_only():
    [m] = parse_staff(STAFF)
    assert m["name"] == "Mikel Arteta" and m["role"] == "manager"
    assert m["joined"] == "2019-12-22" and m["from_tm_id"] == "281" and m["from_name"] == "Manchester City"


def test_parse_league_lists_clubs():
    assert parse_league(LEAGUE) == {"11": "Arsenal FC", "631": "Chelsea FC"}


@pytest.mark.parametrize("status, html", [(403, ""), (429, ""), (200, "<title>Just a moment...</title>")])
def test_bot_check_stops_the_run(status, html):
    with pytest.raises(Blocked):
        check_blocked(status, html)


def test_normal_page_is_not_blocked():
    check_blocked(200, "<html><title>Arsenal FC - Squad</title></html>")


# --- revenge flags ---

def test_months_before_clamps_month_end():
    assert months_before(date(2026, 10, 25), 18) == date(2025, 4, 25)
    assert months_before(date(2026, 3, 31), 1) == date(2026, 2, 28)


@pytest.fixture
def registry(tmp_path):
    csv = tmp_path / "teams.csv"
    csv.write_text("canonical_name,country,aliases,football_data_id,api_football_id,transfermarkt_id,espn_id\n"
                   "Arsenal,England,Arsenal FC,57,,11,\n"
                   "Chelsea,England,Chelsea FC,61,,631,\n"
                   "Brentford,England,Brentford FC,402,,,\n"
                   "Celtic,Scotland,Celtic FC,,,371,\n", encoding="utf-8")
    return Registry(csv)


def person(name, from_id, joined, role="player", transfer="transfer"):
    return {"name": name, "tm_id": name, "role": role, "joined": joined,
            "from_tm_id": from_id, "from_name": "x", "transfer": transfer}


SNAPSHOT = {"clubs": [
    {"tm_id": "11", "name": "Arsenal FC", "people": [
        person("Recent Signing", "631", "2025-08-01"),
        person("Old Signing", "631", "2024-07-01"),
        person("Loanee", "631", "2026-09-01", transfer="loan"),
        person("From Brentford", "1148", "2026-07-01"),
        person("Ex Celtic", "371", "2026-01-15"),
    ]},
    {"tm_id": "631", "name": "Chelsea FC", "people": [
        person("The Manager", "11", "2026-06-01", role="manager"),
        person("No Date", "11", None),
    ]},
    {"tm_id": "1148", "name": "Brentford FC", "people": []},
]}


def make(registry, config, **cfg):
    return Revenge(SNAPSHOT, registry, {**config["signals"]["revenge"], **cfg})


def names(flags):
    return sorted(f["person"] for f in flags)


def test_flags_both_directions_within_window(registry, config):
    flags = make(registry, config, transfer_window_months=18).flags("Arsenal", "Chelsea", KICKOFF)
    assert names(flags) == ["Recent Signing", "The Manager"]
    manager = next(f for f in flags if f["role"] == "manager")
    assert manager["team"] == "Chelsea" and manager["from"] == "Arsenal"


def test_window_is_configurable(registry, config):
    flags = make(registry, config, transfer_window_months=36).flags("Chelsea", "Arsenal", KICKOFF)
    assert "Old Signing" in names(flags)


def test_current_loans_only_count_when_enabled(registry, config):
    assert "Loanee" not in names(make(registry, config).flags("Arsenal", "Chelsea", KICKOFF))
    flags = make(registry, config, include_current_loans=True).flags("Arsenal", "Chelsea", KICKOFF)
    assert "Loanee" in names(flags)


def test_club_matched_by_name_when_csv_has_no_id(registry, config):
    # Brentford has no transfermarkt_id in teams.csv; the snapshot's name ties it up.
    assert names(make(registry, config).flags("Brentford", "Arsenal", KICKOFF)) == ["From Brentford"]


def test_opponent_outside_the_7_leagues_uses_csv_id(registry, config):
    assert names(make(registry, config).flags("Arsenal", "Celtic", KICKOFF)) == ["Ex Celtic"]


def test_no_snapshot_means_no_flags(registry, config):
    assert Revenge(None, registry, config["signals"]["revenge"]).flags("Arsenal", "Chelsea", KICKOFF) == []


def test_unmatched_snapshot_club_is_logged(registry, config):
    warnings = []
    Revenge({"clubs": [{"tm_id": "9", "name": "Nowhere United", "people": []}]}, registry,
            config["signals"]["revenge"], warnings)
    assert warnings and "Nowhere United" in warnings[0]


def test_signal_prefers_player_over_manager(config):
    cfg = config["signals"]["revenge"]
    value, (key, values) = signal_revenge({"revenge": [{"person": "M", "role": "manager"},
                                                       {"person": "P", "role": "player"}]}, cfg)
    assert value == cfg["player"] and values == {"person": "P", "team": None}
