"""Load the power plant list and the lists of expected additions and closures into SQLite.

Ids: the main list identifies units by a MaStR number (SEE...) or, for some older records, a
Bundesnetzagentur number (BNA...). Both go into `unit_id`. Ids are stored as published
(`raw_unit_id`) and with surrounding whitespace removed (`unit_id`), so that hidden whitespace can
be reported instead of silently fixed.
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from pathlib import Path

PLANT_COLUMNS = {
    "Datensatztyp*": "record_type",
    "EinheitMastrNummer": "raw_unit_id",
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
SHEET = "Zu- und Rückbau einzeln"

# Expected header cells of the two tables on the sheet (by column position, 0-based).
ADDITIONS_HEADER = {1: "MaStR-Nr.", 2: "Anlagenbetreiber", 3: "Anlagenname", 4: "PLZ", 5: "Ort",
                    6: "Auswertung Energieträger", 7: "Nettonennleistung",
                    8: "Voraussichtliche Aufnahme"}  # fmt: skip
CLOSURES_HEADER = {1: "MaStR-Nr.", 2: "Anlagenbetreiber", 3: "Anlagenname", 4: "PLZ", 5: "Ort",
                   6: "Kategorie der erwarteten Stilllegung", 7: "Auswertung Energieträger",
                   8: "Leistung in MW"}  # fmt: skip

# Reference values. Energy carriers with the renewable flag they should carry; None = no fixed
# answer (waste is partly biogenic; storage, heat and hydrogen depend on the source).
CARRIERS = {
    "Biomasse": "Ja", "Geothermie": "Ja", "SolareStrahlungsenergie": "Ja", "Wasser": "Ja",
    "Wind (offshore)": "Ja", "Wind (onshore)": "Ja",
    "Braunkohle": "Nein", "Erdgas": "Nein", "Grubengas": "Nein", "Kernenergie": "Nein",
    "Mineraloelprodukte": "Nein", "Steinkohle": "Nein",
    "Sonstige Energietraeger (nicht erneuerbar)": "Nein",
    "Abfall": None, "Batteriespeicher": None, "Pumpspeicher": None, "Waerme": None,
    "Wasserstoff": None,
}  # fmt: skip
STATUSES = {
    "InBetrieb": "operating",
    "Netzreserve aufgrund § 13b EnWG": "reserve",
    "Netzreserve aufgrund von KVBG": "reserve",
    "Kapazitätsreserve aufgrund von § 13e EnWG": "reserve",
    "besonderes netztechnisches Betriebsmittel": "reserve",
    "vorläufig Stillgelegt": "temporarily closed",
    "zeitl. gestreckte Stilllegung aufgrund § 50 KVBG": "closing",
    "endgültig stillgelegt nach KVBG": "closed",
    "endgültig stillgelegt nach § 13b EnWG": "closed",
    "endgültig stillgelegt ohne § 13b EnWG oder KVBG": "closed",
}
RECORD_TYPES = {"Einzelanlage", "stillgelegte Anlagen", "Kleinanlagen_aggregiert"}

SCHEMA = """
CREATE TABLE plants (
    record_type TEXT, raw_unit_id TEXT, unit_id TEXT, is_unit INTEGER, operator TEXT, name TEXT,
    state TEXT, country TEXT, year_commissioned INTEGER, year_decommissioned INTEGER, status TEXT,
    energy_carrier TEXT, main_fuel TEXT, renewable TEXT, gross_mw REAL, net_mw REAL
);
CREATE TABLE additions (
    raw_unit_id TEXT, unit_id TEXT, operator TEXT, name TEXT, postcode TEXT, place TEXT,
    energy_carrier TEXT, net_mw REAL, expected_year INTEGER
);
CREATE TABLE closures (
    raw_unit_id TEXT, unit_id TEXT, operator TEXT, name TEXT, postcode TEXT, place TEXT,
    category TEXT, energy_carrier TEXT, mw REAL
);
CREATE TABLE carriers (energy_carrier TEXT PRIMARY KEY, renewable_expected TEXT);
CREATE TABLE statuses (status TEXT PRIMARY KEY, kind TEXT);
CREATE TABLE record_types (record_type TEXT PRIMARY KEY);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def german_number(text: str):
    """'1.234,5' -> 1234.5; '' -> None. The file uses a decimal comma and dot thousands."""
    text = (text or "").strip()
    if not text:
        return None
    return float(text.replace(".", "").replace(",", "."))


def clean_id(raw):
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def read_plant_csv(text: str) -> tuple[list[dict], str]:
    """Parse the BNetzA CSV (semicolon, decimal comma, a few title lines before the header).

    Returns the rows with English column names and the data date ("Datenstand").
    """
    lines = text.splitlines()
    header = next((i for i, line in enumerate(lines) if line.startswith("Datensatztyp")), None)
    if header is None:
        raise ValueError(
            "no header line starting with 'Datensatztyp' found; has the format changed?"
        )
    present = set(next(csv.reader([lines[header]], delimiter=";")))
    absent = [c for c in PLANT_COLUMNS if c not in present]
    if absent:
        raise ValueError(f"columns missing from the power plant list: {absent}")
    m = re.search(r"Datenstand:\s*(\d{2}\.\d{2}\.\d{4})", "\n".join(lines[:header]))
    if not m:
        raise ValueError("no 'Datenstand: DD.MM.YYYY' found above the header")

    rows = []
    for raw in csv.DictReader(io.StringIO("\n".join(lines[header:])), delimiter=";"):
        if not any((v or "").strip() for v in raw.values() if isinstance(v, str)):
            continue  # blank line
        row = {}
        for de, en in PLANT_COLUMNS.items():
            value = raw.get(de)
            if en == "raw_unit_id":
                row[en] = value if (value or "").strip() else None
            elif en in NUMERIC:
                number = german_number(value)
                row[en] = int(number) if (number is not None and en.startswith("year")) else number
            else:
                row[en] = (value or "").strip() or None
        row["unit_id"] = clean_id(row["raw_unit_id"])
        # a unit record has an id or a name; rows with neither are aggregates
        row["is_unit"] = int(row["unit_id"] is not None or row["name"] is not None)
        rows.append(row)
    return rows, m.group(1)


def _check_header(row, expected: dict, table: str) -> None:
    for col, start in expected.items():
        cell = row[col] if col < len(row) else None
        if not (isinstance(cell, str) and cell.strip().startswith(start)):
            raise ValueError(f"{table} table: column {col} is {cell!r}, expected '{start}...'")


def read_change_lists(path: str | Path) -> tuple[list[dict], list[dict]]:
    """Rows of the two tables on the sheet "Zu- und Rückbau einzeln".

    The sheet holds expected additions (in construction or test operation) and, further down,
    expected closures, with different column orders. Header cells are checked, so a reordered
    sheet fails loudly. Every row with an operator or a name is kept, with or without an id
    (new units often have no MaStR number yet).
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    if SHEET not in wb.sheetnames:
        raise ValueError(f"sheet {SHEET!r} not found; sheets are {wb.sheetnames}")
    additions, closures, table = [], [], None
    for r in wb[SHEET].iter_rows(values_only=True):
        r = tuple(r) + (None,) * (10 - len(r))
        first = r[1]
        if isinstance(first, str) and first.strip().startswith("MaStR-Nr."):
            text = " ".join(str(c) for c in r if c)
            table = "closures" if "Kategorie" in text else "additions"
            _check_header(r, CLOSURES_HEADER if table == "closures" else ADDITIONS_HEADER, table)
            continue
        if isinstance(first, str) and first.startswith("*"):
            table = None  # footnote ends a table
            continue
        if table is None or not (r[2] or r[3]):
            continue
        raw = first if isinstance(first, str) and first.strip() else None
        common = {"raw_unit_id": raw, "unit_id": clean_id(raw), "operator": r[2], "name": r[3],
                  "postcode": None if r[4] is None else str(r[4]), "place": r[5]}  # fmt: skip
        if table == "additions":
            additions.append(
                common | {"energy_carrier": r[6], "net_mw": r[7], "expected_year": r[8]}
            )
        else:
            closures.append(common | {"category": r[6], "energy_carrier": r[7], "mw": r[8]})
    if not additions or not closures:
        raise ValueError("expected both an additions table and a closures table on the sheet")
    return additions, closures


def build_db(plants, additions, closures, data_date, db=":memory:"):
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    for table, items in (("plants", plants), ("additions", additions), ("closures", closures)):
        cols = [c[1] for c in con.execute(f"PRAGMA table_info({table})")]
        con.executemany(
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [tuple(item.get(c) for c in cols) for item in items],
        )
    con.executemany("INSERT INTO carriers VALUES (?, ?)", CARRIERS.items())
    con.executemany("INSERT INTO statuses VALUES (?, ?)", STATUSES.items())
    con.executemany("INSERT INTO record_types VALUES (?)", [(t,) for t in RECORD_TYPES])
    con.execute("INSERT INTO meta VALUES ('data_date', ?)", (data_date,))
    con.commit()
    return con


def decode(data: bytes) -> str:
    """The file is published in a Windows encoding (cp1252/Latin-1). If a later release is UTF-8,
    use that instead of silently garbling every umlaut."""
    for encoding in ("utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin1")  # never fails


def load_files(raw_dir: str | Path = "data/raw", db=":memory:"):
    raw = Path(raw_dir)
    plants, data_date = read_plant_csv(decode((raw / "kraftwerksliste.csv").read_bytes()))
    additions, closures = read_change_lists(raw / "zu_und_rueckbau.xlsx")
    return build_db(plants, additions, closures, data_date, db)
