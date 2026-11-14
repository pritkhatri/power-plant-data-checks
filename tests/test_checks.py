"""Every rule branch has a case that must be flagged and, where it matters, one that must not.

The tables are tiny and synthetic (test data only).
"""

import csv

import pytest

from ppcheck.load import build_db
from ppcheck.run import run_checks, write_results


def unit(unit_id, **kw):
    row = dict(
        record_type="Einzelanlage", raw_unit_id=unit_id, unit_id=unit_id, is_unit=1, operator="Op",
        name=f"Plant {unit_id}", state="NordrheinWestfalen", country="Deutschland",
        year_commissioned=2000, year_decommissioned=None, status="InBetrieb",
        energy_carrier="Erdgas", main_fuel="Erdgas", renewable="Nein", gross_mw=100.0, net_mw=95.0,
    )  # fmt: skip
    row.update(kw)
    return row


CLOSED = "endgültig stillgelegt nach KVBG"
AGGREGATE = unit(None, record_type="Kleinanlagen_aggregiert", is_unit=0, operator=None, name=None,
                 year_commissioned=None, gross_mw=0.0, net_mw=0.0, state=None)  # fmt: skip


def change(unit_id, raw=None, **kw):
    return {"raw_unit_id": raw if raw is not None else unit_id, "unit_id": unit_id,
            "operator": "Op", "name": f"Plant {unit_id}", **kw}  # fmt: skip


@pytest.fixture
def results():
    plants = [
        unit("SEE1"),  # clean
        # missing
        unit(None, name="No id"),
        unit("M2", name=None),
        unit("M3", status=None, operator=None),  # no status, and no operator on a non-closed unit
        unit("M4", energy_carrier=None),
        unit("M5", net_mw=None),
        unit("M6", gross_mw=None),
        unit("M7", year_commissioned=None),
        unit("M8", country=None),
        unit("M9", state=None),
        unit("M10", state=None, country="Oesterreich"),  # fine: abroad
        unit("M11", status=CLOSED, operator=None),  # only the decommissioning year is missing
        unit("M12", status=CLOSED, operator=None, year_decommissioned=2020),  # fine
        # inconsistent
        unit("I1", net_mw=120.0),
        unit("I2", net_mw=0.0),
        unit("I3", status=CLOSED, year_commissioned=2010, year_decommissioned=2005),
        unit("I4", year_commissioned=2030),
        unit("I5", year_decommissioned=2020),  # in operation with a decommissioning year
        unit("I6", energy_carrier="Biomasse", renewable="Nein"),
        unit("I7", energy_carrier="Abfall", renewable="Ja"),  # fine: no fixed answer for waste
        unit("I8", raw_unit_id="I8 "),
        # duplicates
        unit("D1"),
        unit("D1"),  # same id twice (different rows)
        unit(
            "D2", name="Twin", net_mw=50.0, operator=None, status=CLOSED, year_decommissioned=2010
        ),
        unit(
            "D3", name="Twin", net_mw=50.0, operator=None, status=CLOSED, year_decommissioned=2011
        ),
        unit("D4", name="Twin", net_mw=60.0),  # fine: other capacity
        # cross source
        unit("X1", status="Netzreserve aufgrund § 13b EnWG"),
        unit("X2", status=CLOSED, year_decommissioned=2024),
        unit("X3", name="Renamed plant"),
        unit("BOTH"),
        # vocabulary
        unit("V1", energy_carrier="Kernfusion"),
        unit("V2", status="im Bau"),
        unit("V3", renewable="vielleicht"),
        AGGREGATE,  # never checked
    ]
    additions = [
        change("X1", expected_year=2027),
        change(None, raw=None, name="No id yet", expected_year=2027),  # kept, not flagged
        change("A2", raw="\tA2"),
        change("BOTH"),
    ]
    closures = [
        change("X2"),
        change("GHOST", name="Ghost plant"),
        change("OLDID", name="Renamed plant"),  # in the main list as X3
        change("BOTH"),
    ]
    con = build_db(plants, additions, closures, "26.06.2026")
    return run_checks(con)


def ids(rows, issue_part):
    return sorted(str(r["unit_id"]) for r in rows if issue_part in r["issue"])


@pytest.mark.parametrize(
    "issue, expected",
    [
        ("no unit id", ["None"]),
        ("no name", ["M2"]),
        ("no status", ["M3"]),
        ("no operator", ["M3"]),  # M11 and M12 are closed: not flagged
        ("no energy carrier", ["M4"]),
        ("no net capacity", ["M5"]),
        ("no gross capacity", ["M6"]),
        ("no commissioning year", ["M7"]),
        ("no country", ["M8"]),
        ("federal state", ["M9"]),  # M10 is abroad
        ("no decommissioning year", ["M11"]),
    ],
)
def test_missing(results, issue, expected):
    assert ids(results["missing"], issue) == expected


@pytest.mark.parametrize(
    "issue, expected",
    [
        ("net capacity above gross", ["I1"]),
        ("not positive", ["I2"]),  # the aggregate with 0 MW is not a unit
        ("decommissioned before commissioned", ["I3"]),
        ("after the data date", ["I4"]),
        ("in operation but has a decommissioning year", ["I5"]),
        ("renewable flag", ["I6"]),  # I7 (waste) has no fixed answer
        ("main list has whitespace", ["I8"]),
        ("expected additions has whitespace", ["A2"]),
    ],
)
def test_inconsistent(results, issue, expected):
    assert ids(results["inconsistent"], issue) == expected


def test_duplicates(results):
    rows = results["duplicates"]
    assert ids(rows, "more than once") == ["D1", "D1"]
    # D2 and D3 have no operator: matched NULL-safely; D4 has another capacity
    assert ids(rows, "same operator, name") == ["D2", "D3"]


@pytest.mark.parametrize(
    "issue, expected",
    [
        ("expected addition, but", ["X1"]),
        ("already permanently closed", ["X2"]),
        ("not found in the main list", ["GHOST"]),
        ("under a different id", ["OLDID"]),
        ("addition and as expected closure", ["BOTH"]),
    ],
)
def test_cross_source(results, issue, expected):
    assert ids(results["cross_source"], issue) == expected


@pytest.mark.parametrize(
    "issue, expected",
    [("energy carrier", ["V1"]), ("unknown status", ["V2"]), ("Ja/Nein", ["V3"])],
)
def test_vocabulary(results, issue, expected):
    assert ids(results["vocabulary"], issue) == expected


def test_clean_unit_is_never_flagged(results):
    assert all(r["unit_id"] != "SEE1" for rows in results.values() for r in rows)


def test_write_results_files(tmp_path):
    con = build_db(
        [unit("SEE1"), unit("SEE2", net_mw=120.0)],
        [change("SEE3"), change(None, name="New unit")],
        [change("SEE4", name="Gone")],
        "26.06.2026",
    )
    write_results(run_checks(con), con, tmp_path)
    rows = list(csv.DictReader(open(tmp_path / "worklist.csv", encoding="utf-8")))
    assert {r["unit_id"] for r in rows} == {"SEE2", "SEE4"}
    assert {r["check_name"] for r in rows} == {"inconsistent", "cross_source"}
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "26.06.2026" in summary and "| missing | (none found) | 0 |" in summary
    assert "Expected additions: 2, of which 1 have no id" in summary


def test_closure_whitespace_and_record_type_on_all_rows():
    plants = [
        unit("SEE1"),
        unit(
            None,
            record_type=None,
            is_unit=0,
            name=None,
            operator=None,
            energy_carrier="Wind (offshore)",
        ),
        unit(None, record_type="Sonderfall", is_unit=0, name=None, operator=None),
        AGGREGATE,  # a known record type: fine
    ]
    closures = [change("SEE1", raw="SEE1\t"), change("NONAME", name=None)]
    results = run_checks(build_db(plants, [], closures, "26.06.2026"))
    assert ids(results["inconsistent"], "expected closures has whitespace") == ["SEE1"]
    assert len([r for r in results["vocabulary"] if "record type" in r["issue"]]) == 2
    # a closure with an unknown id and no name is still reported
    assert ids(results["cross_source"], "not found in the main list") == ["NONAME"]


def test_decode_prefers_utf8_and_falls_back():
    from ppcheck.load import decode

    assert decode("Niederaußem".encode()) == "Niederaußem"
    assert decode("Niederaußem".encode("latin1")) == "Niederaußem"


def test_closure_name_match_needs_compatible_operator():
    plants = [unit("P1", name="Heizkraftwerk", operator="Stadtwerke A")]
    closures = [
        change("C1", name="Heizkraftwerk", operator="Stadtwerke A"),  # same plant, other id
        change("C2", name="Heizkraftwerk", operator="Energie B"),  # only the name is shared
    ]
    rows = run_checks(build_db(plants, [], closures, "26.06.2026"))["cross_source"]
    assert ids(rows, "under a different id") == ["C1"]
    assert ids(rows, "not found in the main list") == []  # the name exists, so C2 is not "absent"


def test_duplicate_detail_shows_technology():
    plants = [unit("T1", name="Block", technology="GasturbinenmitAbhitzekessel"),
              unit("T2", name="Block", technology="GasturbinenmitAbhitzekessel")]  # fmt: skip
    rows = run_checks(build_db(plants, [], [], "26.06.2026"))["duplicates"]
    assert all("GasturbinenmitAbhitzekessel" in r["detail"] for r in rows)


def test_impact_counts_capacity_and_whether_it_is_closed():
    from ppcheck.impact import capacity_in_service, impact

    plants = [
        unit("A1", net_mw=120.0, gross_mw=100.0),  # net above gross, in operation: 120 MW
        unit("A2", net_mw=80.0, gross_mw=70.0, status=CLOSED, year_decommissioned=2013),  # closed
        # three identical units: two of them could be double-counted (2 x 50 MW), one is closed
        unit("T1", name="Twin", net_mw=50.0),
        unit("T2", name="Twin", net_mw=50.0),
        unit("T3", name="Twin", net_mw=50.0, status=CLOSED, year_decommissioned=2010),
        # no record type, in operation, no id: found again through its record type
        unit(None, record_type=None, is_unit=0, name=None, operator=None, net_mw=500.0),
    ]
    con = build_db(plants, [], [change("GONE", name="Gone", mw=23.4)], "26.06.2026")
    rows = {(e["check"], e["issue"]): e for e in impact(con, run_checks(con))}

    over = rows[("inconsistent", "net capacity above gross capacity")]
    assert (over["findings"], over["mw"], over["mw_not_closed"]) == (2, 200.0, 120.0)

    twins = rows[("duplicates", "same operator, name, capacity and year as another unit")]
    assert (twins["findings"], twins["mw"]) == (3, 100.0)  # n - 1 = 2 units of 50 MW
    assert twins["mw_not_closed"] == 100.0  # two are not closed, so both could be in service

    record = rows[("vocabulary", "missing or unknown record type")]
    assert (record["mw"], record["mw_not_closed"]) == (500.0, 500.0)

    gone = rows[("cross_source", "expected closure not found in the main list, by id or by name")]
    assert gone["mw"] == 23.4  # taken from the list of expected closures

    # in service: A1 120 + T1 50 + T2 50 + the 500 MW row; the two closed units are left out
    assert capacity_in_service(con) == 720.0


def test_capacity_ratio_flags_only_low_nonclosed_units_and_preserves_operator():
    from ppcheck.impact import impact

    plants = [
        unit("CR1", operator="Wuppertal Energie", net_mw=40.0, gross_mw=100.0),
        unit("CR2", net_mw=90.0, gross_mw=100.0),  # normal ratio
        unit("CR3", net_mw=40.0, gross_mw=100.0, status=CLOSED),  # closed
        unit("CR4", net_mw=0.0, gross_mw=0.0),  # ratio is undefined
        unit("CR5", net_mw=40.0, gross_mw=100.0, status="unclassified status"),
    ]
    con = build_db(plants, [], [], "26.06.2026")
    results = run_checks(con)

    rows = results["capacity_ratio"]
    assert [row["unit_id"] for row in rows] == ["CR1", "CR5"]
    assert rows[0]["operator"] == "Wuppertal Energie"
    assert "net 40.0 MW, gross 100.0 MW" in rows[0]["detail"]

    entry = next(e for e in impact(con, results) if e["check"] == "capacity_ratio")
    assert (entry["findings"], entry["mw"], entry["mw_not_closed"]) == (2, 80.0, 80.0)
