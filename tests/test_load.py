import openpyxl

from ppcheck.load import german_number, read_change_lists, read_plant_csv

CSV = (
    ";;;\n"
    ";Quelle: Marktstammdatenregister Datenstand: 26.06.2026;;\n"
    "Datensatztyp*;EinheitMastrNummer;Anlagenbetreiber;Anzeigename;Bundesland;Land;"
    "Jahr_Inbetriebnahme;Jahr_Stilllegung**;Kraftwerksstatus;Energietraeger;Hauptbrennstoff;"
    "Erneuerbarer_Energietraeger;Bruttoleistung_MW;Nettonennleistung_MW\n"
    "Einzelanlage;SEE1;Op;A;Bayern;Deutschland;1998;;InBetrieb;Erdgas;Erdgas;Nein;1.234,5;1.200\n"
    "stillgelegte Anlagen;;;;Bayern;Deutschland;;;endgültig stillgelegt;Erdgas;;Nein;42,4;41,9\n"
)


def test_german_number():
    assert german_number("1.234,5") == 1234.5
    assert german_number("") is None


def test_read_plant_csv_header_date_and_numbers():
    rows, data_date = read_plant_csv(CSV)
    assert data_date == "26.06.2026"
    assert len(rows) == 2
    assert rows[0]["gross_mw"] == 1234.5 and rows[0]["year_commissioned"] == 1998
    assert rows[1]["mastr_id"] is None  # aggregate row kept, without an id


def test_read_change_lists_splits_tables_and_strips_ids(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Zu- und Rückbau einzeln"
    ws.append([None, "MaStR-Nr. der Stromerzeugungseinheit (falls bereits vorhanden)", "Betreiber"])
    ws.append([None, "\tSEE1", "Op", "New", 1, "X", "Erdgas", 60, 2026])
    ws.append([None, "*Angaben sind nicht verbindlich"])
    ws.append([None, "MaStR-Nr. der Stromerzeugungseinheit", "Betreiber", "Name", "PLZ", "Ort",
               "Kategorie der erwarteten Stilllegung", "Energieträger", "MW"])  # fmt: skip
    ws.append([None, "SEE2", "Op", "Old", 1, "Y", "KVBG", "Braunkohle", 465])
    path = tmp_path / "zr.xlsx"
    wb.save(path)
    additions, closures = read_change_lists(path)
    assert [(a["raw_id"], a["mastr_id"], a["expected_year"]) for a in additions] == [
        ("\tSEE1", "SEE1", 2026)
    ]
    assert [(c["mastr_id"], c["energy_carrier"], c["mw"]) for c in closures] == [
        ("SEE2", "Braunkohle", 465)
    ]
