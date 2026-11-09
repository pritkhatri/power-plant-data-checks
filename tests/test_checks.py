"""One test per check, on a tiny synthetic table with known defects (test data only)."""

import pytest

from ppcheck.load import build_db
from ppcheck.run import run_checks


def unit(mastr_id, **kw):
    row = dict(
        record_type="Einzelanlage", mastr_id=mastr_id, operator="Op", name=f"Plant {mastr_id}",
        state="NordrheinWestfalen", country="Deutschland", year_commissioned=2000,
        year_decommissioned=None, status="InBetrieb", energy_carrier="Erdgas", main_fuel="Erdgas",
        renewable="Nein", gross_mw=100.0, net_mw=95.0,
    )  # fmt: skip
    row.update(kw)
    return row


AGGREGATE = unit(None, record_type="Kleinanlagen_aggregiert", operator=None, name=None,
                 year_commissioned=None, gross_mw=0.0, net_mw=0.0)  # fmt: skip


@pytest.fixture
def results():
    plants = [
        unit("SEE1"),  # clean
        unit("SEE2", year_commissioned=None),  # missing
        unit("SEE3", state=None),  # missing (in Germany)
        unit("SEE4", state=None, country="Oesterreich"),  # fine: abroad
        unit("SEE5", status="endgültig stillgelegt nach KVBG", operator=None),  # missing year only
        unit("SEE6", net_mw=120.0),  # inconsistent: net > gross
        unit("SEE7", energy_carrier="Biomasse", renewable="Nein"),  # inconsistent flag
        unit("SEE8", name="Twin", net_mw=50.0),  # duplicate candidates
        unit("SEE9", name="Twin", net_mw=50.0),
        unit("SEE10", status="endgültig stillgelegt nach § 13b EnWG", year_decommissioned=2024),
        unit("SEE11", status="Netzreserve aufgrund § 13b EnWG"),
        AGGREGATE,  # never checked
    ]
    additions = [
        {"raw_id": "SEE11", "mastr_id": "SEE11", "name": "New?", "expected_year": 2027},
        {"raw_id": "\tSEE20", "mastr_id": "SEE20", "name": "Brand new", "expected_year": 2027},
    ]
    closures = [
        {"raw_id": "SEE10", "mastr_id": "SEE10", "name": "Old"},  # already closed
        {"raw_id": "SEE99", "mastr_id": "SEE99", "name": "Ghost"},  # not in main list
    ]
    con = build_db(plants, additions, closures, "26.06.2026")
    return run_checks(con)


def ids(rows, issue_part=""):
    return sorted(r["mastr_id"] for r in rows if issue_part in r["issue"])


def test_missing(results):
    rows = results["missing"]
    assert ids(rows, "no commissioning year") == ["SEE2"]
    assert ids(rows, "federal state") == ["SEE3"]  # SEE4 is abroad
    assert ids(rows, "decommissioning year") == ["SEE5"]
    assert ids(rows, "no operator") == []  # decommissioned units may lack an operator
    assert None not in ids(rows)  # aggregates are not checked


def test_inconsistent(results):
    rows = results["inconsistent"]
    assert ids(rows, "net capacity above gross") == ["SEE6"]
    assert ids(rows, "renewable flag") == ["SEE7"]
    assert ids(rows, "whitespace") == ["SEE20"]
    assert ids(rows, "not positive") == []  # the aggregate with 0 MW is not a unit


def test_duplicates(results):
    assert ids(results["duplicates"]) == ["SEE8", "SEE9"]


def test_cross_source(results):
    rows = results["cross_source"]
    assert ids(rows, "expected addition, but") == ["SEE11"]
    assert ids(rows, "already permanently decommissioned") == ["SEE10"]
    assert ids(rows, "not found in the main list") == ["SEE99"]
