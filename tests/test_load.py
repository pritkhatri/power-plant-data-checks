import openpyxl
import pytest

from ppcheck.load import (
    ADDITIONS_HEADER,
    CLOSURES_HEADER,
    german_number,
    read_change_lists,
    read_plant_csv,
)

CSV = (
    ";;;\n"
    ";Quelle: Marktstammdatenregister Datenstand: 26.06.2026;;\n"
    "Datensatztyp*;EinheitMastrNummer;Anlagenbetreiber;Anzeigename;Bundesland;Land;"
    "Jahr_Inbetriebnahme;Jahr_Stilllegung**;Kraftwerksstatus;Energietraeger;Hauptbrennstoff;"
    "Erneuerbarer_Energietraeger;Bruttoleistung_MW;Nettonennleistung_MW\n"
    "Einzelanlage;SEE1;Op;A;Bayern;Deutschland;1998;;InBetrieb;Erdgas;Erdgas;Nein;1.234,5;1.200\n"
    "stillgelegte Anlagen;BNA0705 ;;B;Bayern;Deutschland;1970;2010;endgültig stillgelegt;Erdgas;;"
    "Nein;95;113\n"
    "stillgelegte Anlagen;;;;Bayern;Deutschland;;;endgültig stillgelegt;Erdgas;;Nein;42,4;41,9\n"
)


def test_german_number():
    assert german_number("1.234,5") == 1234.5
    assert german_number("95") == 95.0
    assert german_number("") is None


def test_read_plant_csv():
    rows, data_date = read_plant_csv(CSV)
    assert data_date == "26.06.2026"
    assert len(rows) == 3
    assert rows[0]["gross_mw"] == 1234.5 and rows[0]["year_commissioned"] == 1998
    # the id with a trailing space is kept as published and cleaned separately
    assert (rows[1]["raw_unit_id"], rows[1]["unit_id"], rows[1]["is_unit"]) == (
        "BNA0705 ",
        "BNA0705",
        1,
    )
    assert (rows[1]["gross_mw"], rows[1]["net_mw"]) == (95.0, 113.0)
    # no id and no name: an aggregate
    assert (rows[2]["unit_id"], rows[2]["is_unit"]) == (None, 0)


def test_changed_csv_layout_fails_loudly():
    with pytest.raises(ValueError, match="Nettonennleistung_MW"):
        read_plant_csv(CSV.replace("Nettonennleistung_MW", "Netto_MW"))
    with pytest.raises(ValueError, match="header"):
        read_plant_csv("no;header;here\n1;2;3\n")
    with pytest.raises(ValueError, match="Datenstand"):
        read_plant_csv(CSV.replace("Datenstand: 26.06.2026", "Stand: Juni"))


def header_row(spec):
    row = [None] * 10
    for col, text in spec.items():
        row[col] = text + " x"
    return row


def sheet(tmp_path, closures_header=CLOSURES_HEADER):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Zu- und Rückbau einzeln"
    ws.append(header_row(ADDITIONS_HEADER))
    ws.append([None, "\tSEE1", "Op", "New", 12345, "X", "Erdgas", 60, 2026])
    ws.append([None, None, "Op", "No id yet", 12345, "X", "Erdgas", 400, 2027])
    ws.append([None, "*Angaben sind nicht verbindlich"])
    ws.append(header_row(closures_header))
    ws.append([None, "SEE2", "Op", "Old", 1, "Y", "KVBG", "Braunkohle", 465])
    ws.append([None, None, None, None, "Erwartete Stilllegungen in MW", None, None, None, 465])
    path = tmp_path / "zr.xlsx"
    wb.save(path)
    return path


def test_read_change_lists(tmp_path):
    additions, closures = read_change_lists(sheet(tmp_path))
    assert [(a["raw_unit_id"], a["unit_id"], a["name"], a["expected_year"]) for a in additions] == [
        ("\tSEE1", "SEE1", "New", 2026),
        (None, None, "No id yet", 2027),  # kept although it has no id
    ]
    assert [(c["unit_id"], c["energy_carrier"], c["mw"]) for c in closures] == [
        ("SEE2", "Braunkohle", 465)  # the totals row is not a unit
    ]


def test_reordered_sheet_fails_loudly(tmp_path):
    swapped = dict(CLOSURES_HEADER)
    swapped[7], swapped[8] = CLOSURES_HEADER[8], CLOSURES_HEADER[7]
    with pytest.raises(ValueError, match="closures table: column 7"):
        read_change_lists(sheet(tmp_path, swapped))


def test_missing_sheet_fails_loudly(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Something else"
    path = tmp_path / "zr.xlsx"
    wb.save(path)
    with pytest.raises(ValueError, match="not found"):
        read_change_lists(path)
