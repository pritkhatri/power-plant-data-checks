"""Run all checks and write the work list."""

from __future__ import annotations

import csv
import sqlite3
from importlib import resources
from pathlib import Path

CHECKS = ["missing", "inconsistent", "duplicates", "cross_source"]
FIELDS = ["check_name", "mastr_id", "operator", "name", "field", "issue"]


def run_checks(con: sqlite3.Connection) -> dict[str, list[dict]]:
    out = {}
    for name in CHECKS:
        sql = resources.files("ppcheck").joinpath(f"checks/{name}.sql").read_text()
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        out[name] = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    return out


def write_results(results: dict, con: sqlite3.Connection, out_dir: str | Path = "results") -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "worklist.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for rows in results.values():
            w.writerows(rows)

    n_plants = con.execute("SELECT COUNT(*) FROM plants").fetchone()[0]
    q = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    n_units = q("SELECT COUNT(*) FROM plants WHERE mastr_id IS NOT NULL")
    n_add = q("SELECT COUNT(*) FROM additions")
    n_close = q("SELECT COUNT(*) FROM closures")
    n_add_missing = q(
        "SELECT COUNT(*) FROM additions WHERE mastr_id NOT IN "
        "(SELECT mastr_id FROM plants WHERE mastr_id IS NOT NULL)"
    )
    n_dec_no_op = q(
        "SELECT COUNT(*) FROM plants WHERE mastr_id IS NOT NULL AND operator IS NULL "
        "AND status LIKE 'endgültig stillgelegt%'"
    )
    data_date = con.execute("SELECT value FROM meta WHERE key='data_date'").fetchone()[0]
    lines = [
        f"Data date (Datenstand): {data_date}. Rows in the power plant list: {n_plants}, of which "
        f"{n_units} are unit records with a MaStR id (the rest are aggregates and are not "
        f"checked). Expected additions: {n_add} ({n_add_missing} not yet in the main list, which "
        f"is expected for new units). Expected closures: {n_close}.",
        "",
        f"Not flagged: {n_dec_no_op} permanently decommissioned units are published without an "
        "operator; this looks like a publication choice, not an error.",
        "",
        "| check | issue | rows |",
        "|---|---|---|",
    ]
    for name, rows in results.items():
        if not rows:
            lines.append(f"| {name} | (none found) | 0 |")
        issues: dict[str, int] = {}
        for r in rows:
            key = r["issue"]
            issues[key] = issues.get(key, 0) + 1
        for issue, n in sorted(issues.items()):
            lines.append(f"| {name} | {issue} | {n} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    from .download import download
    from .load import load_files

    download()
    con = load_files("data/raw")
    results = run_checks(con)
    write_results(results, con)
    print(Path("results/summary.md").read_text())


if __name__ == "__main__":
    main()
