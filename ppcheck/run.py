"""Run all checks and write the work list."""

from __future__ import annotations

import csv
import sqlite3
from importlib import resources
from pathlib import Path

from .impact import capacity_in_service, impact

CHECKS = ["missing", "inconsistent", "duplicates", "cross_source", "vocabulary", "capacity_ratio"]
FIELDS = ["check_name", "unit_id", "operator", "name", "status", "field", "issue", "detail"]


def run_checks(con: sqlite3.Connection) -> dict[str, list[dict]]:
    out = {}
    for name in CHECKS:
        sql = resources.files("ppcheck").joinpath(f"checks/{name}.sql").read_text(encoding="utf-8")
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        out[name] = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    return out


def counts(con: sqlite3.Connection) -> dict[str, int | str]:
    def q(sql: str):
        return con.execute(sql).fetchone()[0]

    return {
        "data_date": q("SELECT value FROM meta WHERE key = 'data_date'"),
        "rows": q("SELECT COUNT(*) FROM plants"),
        "units": q("SELECT COUNT(*) FROM plants WHERE is_unit = 1"),
        "bna_ids": q("SELECT COUNT(*) FROM plants WHERE unit_id LIKE 'BNA%'"),
        "bna_closed": q(
            "SELECT COUNT(*) FROM plants p JOIN statuses s ON s.status = p.status "
            "WHERE p.unit_id LIKE 'BNA%' AND s.kind = 'closed'"
        ),
        "closed_mastr": q(
            "SELECT COUNT(*) FROM plants p JOIN statuses s ON s.status = p.status "
            "WHERE p.is_unit = 1 AND s.kind = 'closed' AND p.unit_id LIKE 'SEE%'"
        ),
        "closed_mastr_without_operator": q(
            "SELECT COUNT(*) FROM plants p JOIN statuses s ON s.status = p.status "
            "WHERE p.is_unit = 1 AND s.kind = 'closed' AND p.unit_id LIKE 'SEE%' "
            "AND p.operator IS NULL"
        ),
        "closed_bna_without_operator": q(
            "SELECT COUNT(*) FROM plants p JOIN statuses s ON s.status = p.status "
            "WHERE p.is_unit = 1 AND s.kind = 'closed' AND p.unit_id LIKE 'BNA%' "
            "AND p.operator IS NULL"
        ),
        "additions": q("SELECT COUNT(*) FROM additions"),
        "additions_without_id": q("SELECT COUNT(*) FROM additions WHERE unit_id IS NULL"),
        "additions_not_in_main_list": q(
            "SELECT COUNT(*) FROM additions WHERE unit_id IS NOT NULL AND unit_id NOT IN "
            "(SELECT unit_id FROM plants WHERE unit_id IS NOT NULL)"
        ),
        "closures": q("SELECT COUNT(*) FROM closures"),
        "closures_without_id": q("SELECT COUNT(*) FROM closures WHERE unit_id IS NULL"),
        "closed_without_operator": q(
            "SELECT COUNT(*) FROM plants p JOIN statuses s ON s.status = p.status "
            "WHERE p.is_unit = 1 AND p.operator IS NULL AND s.kind = 'closed'"
        ),
        "closed_units": q(
            "SELECT COUNT(*) FROM plants p JOIN statuses s ON s.status = p.status "
            "WHERE p.is_unit = 1 AND s.kind = 'closed'"
        ),
        "other_without_operator": q(
            "SELECT COUNT(*) FROM plants p LEFT JOIN statuses s ON s.status = p.status "
            "WHERE p.is_unit = 1 AND p.operator IS NULL AND s.kind IS NOT 'closed'"
        ),
        "non_units": ", ".join(
            f"{t or '(no record type)'}: {n}"
            for t, n in con.execute(
                "SELECT record_type, COUNT(*) FROM plants WHERE is_unit = 0 "
                "GROUP BY record_type ORDER BY 2 DESC"
            )
        ),
    }


def write_results(results: dict, con: sqlite3.Connection, out_dir: str | Path = "results") -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "worklist.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for rows in results.values():
            w.writerows(rows)

    c = counts(con)
    lines = [
        f"Data date (Datenstand): {c['data_date']}.",
        "",
        f"- Power plant list: {c['rows']} rows, of which {c['units']} are unit records (an id or "
        f"a name). The other rows have neither and are treated as aggregates ({c['non_units']}); "
        "the unit rules do not apply to them, the vocabulary check does. "
        f"{c['bna_ids']} unit ids are older BNA numbers ({c['bna_closed']} of them on permanently "
        "closed units), the rest MaStR numbers.",
        f"- Expected additions: {c['additions']}, of which {c['additions_without_id']} have no id "
        f"yet and {c['additions_not_in_main_list']} have an id that is not in the main list "
        "(normal for units still being built).",
        f"- Expected closures: {c['closures']}, of which {c['closures_without_id']} have no id.",
        f"- Operator: {c['closed_without_operator']} of {c['closed_units']} permanently closed "
        f"units have none ({c['closed_bna_without_operator']} with a BNA id, "
        f"{c['closed_mastr_without_operator']} of {c['closed_mastr']} with a MaStR id); "
        f"units that are not closed lacking one: {c['other_without_operator']}. "
        "The operator is therefore only required for units that are not closed.",
        "- The vocabulary check compares against reference lists built from this snapshot, so it "
        "guards later downloads; on this snapshot it can only flag rows outside the record types.",
        "",
        "| check | issue | rows |",
        "|---|---|---|",
    ]
    for name, rows in results.items():
        if not rows:
            lines.append(f"| {name} | (none found) | 0 |")
        issues: dict[str, int] = {}
        for r in rows:
            issues[r["issue"]] = issues.get(r["issue"], 0) + 1
        for issue, n in sorted(issues.items()):
            lines.append(f"| {name} | {issue} | {n} |")
    lines += [
        "",
        "Capacity behind the findings (net MW; see `ppcheck/impact.py` for how it is counted). "
        "For scale: all rows that are not permanently closed add up to "
        f"{capacity_in_service(con):,.0f} MW.",
        "",
        "| check | issue | findings | MW at stake | of which not closed |",
        "|---|---|---|---|---|",
    ]
    for e in impact(con, results):
        lines.append(
            f"| {e['check']} | {e['issue']} | {e['findings']} | {e['mw']:,.1f} "
            f"| {e['mw_not_closed']:,.1f} |"
        )
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    import argparse
    import json

    from .download import download
    from .load import load_files

    parser = argparse.ArgumentParser(prog="ppcheck", description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="download the files again")
    args = parser.parse_args(argv)

    source = download(force=args.refresh)
    con = load_files("data/raw")
    results = run_checks(con)
    write_results(results, con)
    data_date = con.execute("SELECT value FROM meta WHERE key = 'data_date'").fetchone()[0]
    # which files these results came from, so a reader can check a later download against them
    Path("results/source.json").write_text(
        json.dumps({"data_date": data_date, "files": source}, indent=2) + "\n", encoding="utf-8"
    )
    print(Path("results/summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
