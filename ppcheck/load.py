"""Load the power plant list and the list of expected additions into SQLite."""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from pathlib import Path

PLANT_COLUMNS = {
    "Datensatztyp*": "record_type",
    "EinheitMastrNummer": "mastr_id",
    "Anlagenbetreiber": "operator",
    "Anzeigename": "name",
    "Bundesland": "state",
    "Land": "country",
    "Jahr_Inbetriebnahme": "year_commissioned",
    "Jahr_Stilllegung**": "year_decommissioned",
    "Kraftwerksstatus": "status",
    "Energietraeger": "energy_carrier",
    "Hauptbrennstoff": "main_fuel",
    "Erneuerbarer_Energietraeger": "renewable",
    "Bruttoleistung_MW": "gross_mw",
    "Nettonennleistung_MW": "net_mw",
}
NUMERIC = {"year_commissioned", "year_decommissioned", "gross_mw", "net_mw"}

SCHEMA = """
CREATE TABLE plants (
    record_type TEXT, mastr_id TEXT, operator TEXT, name TEXT, state TEXT, country TEXT,
    year_commissioned INTEGER, year_decommissioned INTEGER, status TEXT, energy_carrier TEXT,
    main_fuel TEXT, renewable TEXT, gross_mw REAL, net_mw REAL
);
CREATE TABLE additions (
    raw_id TEXT, mastr_id TEXT, operator TEXT, name TEXT, energy_carrier TEXT, net_mw REAL,
    expected_year INTEGER
);
CREATE TABLE closures (
    raw_id TEXT, mastr_id TEXT, operator TEXT, name TEXT, category TEXT, energy_carrier TEXT,
    mw REAL
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def german_number(text: str):
    """'1.234,5' -> 1234.5; '' -> None."""
    text = (text or "").strip()
    if not text:
        return None
    return float(text.replace(".", "").replace(",", "."))


def read_plant_csv(text: str) -> tuple[list[dict], str | None]:
    """Parse the BNetzA CSV (semicolon, decimal comma, a few title lines before the header).

    Returns the rows with English column names and the data date ("Datenstand") if present.
    """
    lines = text.splitlines()
    header = next(i for i, line in enumerate(lines) if line.startswith("Datensatztyp"))
    m = re.search(r"Datenstand:\s*([0-9.]+)", "\n".join(lines[:header]))
    rows = []
    for raw in csv.DictReader(io.StringIO("\n".join(lines[header:])), delimiter=";"):
        if not any((v or "").strip() for v in raw.values() if isinstance(v, str)):
            continue  # blank line
        row = {}
        for de, en in PLANT_COLUMNS.items():
            value = (raw.get(de) or "").strip()
            if en in NUMERIC:
                number = german_number(value)
                value = int(number) if (number is not None and en.startswith("year")) else number
            else:
                value = value or None
            row[en] = value
        rows.append(row)
    return rows, (m.group(1) if m else None)


def read_change_lists(path: str | Path) -> tuple[list[dict], list[dict]]:
    """Unit rows of the two tables on the sheet "Zu- und Rückbau einzeln".

    The sheet holds expected additions (in construction or test operation) and, further down,
    expected closures, with different column orders. A table starts after its header row; a unit
    row is one whose first cell holds a MaStR id. Ids are kept as published (raw_id) and with
    surrounding whitespace removed (mastr_id).
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Zu- und Rückbau einzeln"]
    additions, closures, table = [], [], None
    for r in ws.iter_rows(values_only=True):
        first = r[1]
        if isinstance(first, str) and first.startswith("MaStR-Nr."):
            table = "closures" if "Kategorie" in " ".join(str(c) for c in r if c) else "additions"
            continue
        if not (isinstance(first, str) and first.strip().startswith("SEE")):
            continue
        if table == "additions":
            additions.append(
                {"raw_id": first, "mastr_id": first.strip(), "operator": r[2], "name": r[3],
                 "energy_carrier": r[6], "net_mw": r[7], "expected_year": r[8]}
            )  # fmt: skip
        elif table == "closures":
            closures.append(
                {"raw_id": first, "mastr_id": first.strip(), "operator": r[2], "name": r[3],
                 "category": r[6], "energy_carrier": r[7], "mw": r[8]}
            )  # fmt: skip
    return additions, closures


def build_db(plants, additions, closures, data_date, db=":memory:"):
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    cols = list(PLANT_COLUMNS.values())
    con.executemany(
        f"INSERT INTO plants ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        [tuple(p[c] for c in cols) for p in plants],
    )
    for table, items in (("additions", additions), ("closures", closures)):
        cols = [c[1] for c in con.execute(f"PRAGMA table_info({table})")]
        con.executemany(
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [tuple(item.get(c) for c in cols) for item in items],
        )
    con.execute("INSERT INTO meta VALUES ('data_date', ?)", (data_date,))
    con.commit()
    return con


def load_files(raw_dir: str | Path = "data/raw", db=":memory:"):
    raw = Path(raw_dir)
    plants, data_date = read_plant_csv((raw / "kraftwerksliste.csv").read_bytes().decode("latin1"))
    additions, closures = read_change_lists(raw / "zu_und_rueckbau.xlsx")
    return build_db(plants, additions, closures, data_date, db)
