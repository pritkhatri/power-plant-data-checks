"""How much capacity each kind of finding touches, and how much of it is not closed.

Each finding is matched back to its source row, so its net capacity and status are known. The
numbers answer "does this finding matter for the capacity in service?", which the row counts in
the findings table do not.

What "MW at stake" means:
- most issues: the net capacity of the flagged unit;
- duplicate candidates: the capacity that would be counted twice if every group were a real
  duplicate (n - 1 units per group), not the capacity of all flagged units.

"Not closed" is every status kind except permanently closed (operating, reserve, temporarily
closed, closing), plus units without a status and entries from the lists of expected additions
and closures, which are not closed yet either.
"""

from __future__ import annotations

import sqlite3

DUPLICATE_ISSUE = "same operator, name, capacity and year as another unit"

# Findings without an id can only be found again through what they are about.
EXTRA_CONDITION = {
    "missing or unknown record type": "COALESCE(p.record_type, '') NOT IN "
    "(SELECT record_type FROM record_types)",
}


def _plant_candidates(con: sqlite3.Connection, row: dict) -> list[tuple]:
    extra = EXTRA_CONDITION.get(row["issue"], "1")
    return con.execute(
        "SELECT p.rowid, COALESCE(p.net_mw, 0), s.kind, p.operator, p.name, p.net_mw, "
        "       p.year_commissioned "
        "  FROM plants p LEFT JOIN statuses s ON s.status = p.status "
        f" WHERE p.unit_id IS ? AND p.name IS ? AND p.operator IS ? AND p.status IS ? AND {extra} "
        " ORDER BY p.rowid",
        (row["unit_id"], row["name"], row["operator"], row["status"]),
    ).fetchall()


def _list_entry(con: sqlite3.Connection, unit_id: str | None) -> tuple[float, str] | None:
    """Capacity and kind of an entry in the lists of expected closures or additions."""
    if unit_id is None:
        return None
    hit = con.execute(
        "SELECT COALESCE(mw, 0) FROM closures WHERE unit_id = ?", (unit_id,)
    ).fetchone()
    if hit:
        return hit[0], "expected closure"
    hit = con.execute(
        "SELECT COALESCE(net_mw, 0) FROM additions WHERE unit_id = ?", (unit_id,)
    ).fetchone()
    return (hit[0], "expected addition") if hit else None


def impact(con: sqlite3.Connection, results: dict[str, list[dict]]) -> list[dict]:
    """One row per (check, issue): findings, MW at stake, and the part of it that is not closed."""
    # source rows already matched, per issue: twin rows (same id twice) must not be matched twice,
    # but one unit flagged by two different issues counts for each of them
    used: set[tuple[str, str, int]] = set()
    table: dict[tuple[str, str], dict] = {}
    # duplicate candidates: group key -> [unit MW, kinds of its flagged units]
    groups: dict[tuple, list] = {}

    for check, rows in results.items():
        for r in rows:
            entry = table.setdefault(
                (check, r["issue"]),
                {
                    "check": check,
                    "issue": r["issue"],
                    "findings": 0,
                    "mw": 0.0,
                    "mw_not_closed": 0.0,
                },
            )
            entry["findings"] += 1
            found = next(
                (c for c in _plant_candidates(con, r) if (check, r["issue"], c[0]) not in used),
                None,
            )
            if found is not None:
                used.add((check, r["issue"], found[0]))
                rowid, mw, kind, operator, name, net_mw, year = found
                if r["issue"] == DUPLICATE_ISSUE:
                    key = (check, operator, name, net_mw, year)
                    groups.setdefault(key, [mw, []])[1].append(kind)
                    continue
                entry["mw"] += mw
                entry["mw_not_closed"] += 0.0 if kind == "closed" else mw
                continue
            listed = _list_entry(con, r["unit_id"])
            if listed is not None:
                entry["mw"] += listed[0]
                entry["mw_not_closed"] += listed[0]

    # duplicates: n - 1 units per group could be double-counted; at most as many as are not closed
    dup = table.get(("duplicates", DUPLICATE_ISSUE))
    if dup is not None:
        for mw, kinds in groups.values():
            extra = len(kinds) - 1
            dup["mw"] += extra * mw
            dup["mw_not_closed"] += min(extra, sum(k != "closed" for k in kinds)) * mw

    return sorted(table.values(), key=lambda e: (e["check"], e["issue"]))


def capacity_in_service(con: sqlite3.Connection) -> float:
    """Net MW of all rows (units and aggregates) that are not permanently closed: the base the MW
    at stake is read against."""
    return con.execute(
        "SELECT COALESCE(SUM(p.net_mw), 0) FROM plants p "
        "LEFT JOIN statuses s ON s.status = p.status WHERE s.kind IS NOT 'closed'"
    ).fetchone()[0]
