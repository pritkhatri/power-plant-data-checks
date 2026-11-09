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
