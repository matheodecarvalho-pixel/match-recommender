from datetime import datetime, timezone

from bs4 import BeautifulSoup

from espn_ids import link
from scrape_broadcasters import channels, parse_rows, season_ok, to_codes

TABLE = """
<table class="wikitable">
 <tr><th>Country</th><th>Broadcasters</th></tr>
 <tr><td>France<sup>[a]</sup></td><td><a>Canal+</a><br><a>M6</a><sup>[3]</sup></td></tr>
 <tr><td>United States</td><td rowspan="2">beIN Sports</td></tr>
 <tr><td>Puerto Rico</td></tr>
 <tr><td>Argentina<br>Chile</td><td>ESPN</td></tr>
</table>
"""


def test_rows_handle_rowspan_refs_and_multi_country_cells():
    rows = parse_rows(BeautifulSoup(TABLE, "html.parser").table)
    assert rows == [("France", ["Canal+", "M6"]), ("United States", ["beIN Sports"]),
                    ("Puerto Rico", ["beIN Sports"]), ("Argentina", ["ESPN"]), ("Chile", ["ESPN"])]


def test_linked_channels_on_one_line_are_split():
    cell = BeautifulSoup("<td><a>DAZN</a> <a>Prime Video</a></td>", "html.parser").td
    assert channels(cell) == ["DAZN", "Prime Video"]


def test_season_headings():
    assert season_ok("2024-27", 2026)
    assert not season_ok("2027–2031", 2026)
    assert season_ok("2025–2030", 2026)


def test_country_names_to_codes():
    by_name = {"France": "FR", "Spain": "ES", "Andorra": "AD"}
    assert to_codes("United Kingdom", by_name) == ["GB"]
    assert to_codes("Spain and Andorra", by_name) == ["ES", "AD"]
    assert "EE" in to_codes("Baltics", by_name)
    assert to_codes("Atlantis", by_name) == []


class Reg:
    by_name = {"estrela": "Amadora"}


def test_espn_link_needs_close_kickoff_and_a_shared_team():
    k = datetime(2026, 10, 18, 19, tzinfo=timezone.utc)
    fixture = {"id": "fd-1", "competition": "Primeira Liga", "kickoff_utc": k, "home": "Amadora", "away": "Casa Pia"}
    games = {"Primeira Liga": [
        {"id": "9", "kickoff_utc": "2026-10-18T19:00:00+00:00", "home": "Estrela", "away": "Casa Pia", "us_tv": ["beIN"]},
        {"id": "8", "kickoff_utc": "2026-10-25T19:00:00+00:00", "home": "Estrela", "away": "Casa Pia"},
    ]}
    assert link([fixture], games, Reg())["fd-1"] == {"league": "por.1", "id": "9", "us_tv": ["beIN"]}
