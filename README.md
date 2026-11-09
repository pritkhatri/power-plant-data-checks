# power-plant-data-checks

Data-quality checks in plain SQL on the Bundesnetzagentur power plant list (Kraftwerksliste)
and its lists of expected additions and closures. The checks look for missing, inconsistent,
duplicate and outdated records and write a work list (CSV) with one row per finding, so someone
can go through it and fix or confirm each record.

## Results

Run on the files published with Datenstand 26.06.2026 (`results/source.json` has their
checksums). Counts are from `results/summary.md`, the findings from `results/worklist.csv`, which
shows each unit's status and the values behind each finding.

- Power plant list: 2,614 rows. 2,169 are unit records (they have an id or a name). The other 445
  have neither and are treated as aggregates: 290 "Kleinanlagen_aggregiert" (small units summed
  per state and energy carrier, as the file's footnote defines), 154 "stillgelegte Anlagen" rows
  with state, energy carrier, capacity and status but no id, name, year or operator (the footnote
  does not define these; that they are aggregated closed units is my reading), and 1 row without a
  record type. The unit rules skip these rows; the vocabulary check covers them. 117 of the unit
  ids are older BNA numbers, all of them on permanently closed units, the rest MaStR numbers.
- Expected additions: 37 (10 without an id yet). Expected closures: 40.

| check | finding | rows |
|---|---|---|
| missing | no commissioning year (BNA1337a, closed in 2012) | 1 |
| inconsistent | net capacity above gross capacity (BNA0189 Datteln: net 113 MW, gross 95 MW; closed in 2013) | 1 |
| inconsistent | id published with hidden whitespace: `'BNA0705 '` in the main list, a leading tab before SEE918810715130 in the additions list | 2 |
| duplicates | several ids with the same operator, name, capacity and commissioning year | 28 (10 groups) |
| cross_source | expected closure not found in the main list, by id or by name (Heizkraftwerk Stuttgart-Münster GT 18, 23.4 MW) | 1 |
| vocabulary | row without a record type (offshore wind, Ostsee, 1,522.75 MW) | 1 |

What these numbers mean:

- The list is clean in the checked fields for almost all units. The findings are few, and several
  concern units that closed more than ten years ago (Datteln and BNA1337a closed in 2013 and
  2012). For Datteln the two sister units show 95 MW gross and net, so the 113 MW may be a typing
  error, but the file does not say.
- A duplicate flag is a reason to look, not proof of an error. Six of the ten groups are closed
  units with older BNA ids (for example four Brunsbüttel units of 63.5 MW from 1973), which are
  probably real, identical blocks. Two groups deserve a closer look: "HKW III Block B" of
  Stadtwerke Duisburg has two ids, both in operation, both 75.2 MW net and from 2004 (a third
  record with the same name has 84 MW from 2005); if that is one unit registered twice, it is
  counted twice in operating capacity. "Gasturbine 1 - GuD MPE" has two ids with the same capacity
  and year, one in operation and one temporarily closed.
- Ids with hidden whitespace break a plain join on the id. In this snapshot neither case breaks a
  join between the files (SEE918810715130 is a new unit not yet in the main list, and BNA0705 is in
  no change list), but the loader keeps every id as published and reports where it had to clean
  it.
- Stuttgart-Münster GT 18 is in the list of expected closures, while its sister units GT 16 and
  GT 17 (23.3 MW each) are in the main list and GT 18 is not, under any id or name.
- Operator: 238 of the 266 permanently closed units have none (all 117 with a BNA id and 121 of the
  149 with a MaStR id), while every unit that is not closed has one. So the checks require an
  operator only for units that are not closed, and the summary reports the closed ones as a count.
- The vocabulary reference lists were built from this snapshot, so on this snapshot that check can
  only flag rows outside the record types. Its use is on later downloads.

## The checks

Each check is one SQL file in `ppcheck/checks/` and returns the same columns
(`check_name, unit_id, operator, name, status, field, issue, detail`). The expected values (18
energy carriers with their renewable flag, 10 statuses grouped into operating, reserve,
temporarily closed, closing and closed) are reference tables in `ppcheck/load.py`.

| file | what it looks for |
|---|---|
| `missing.sql` | empty id, name, status, energy carrier, net or gross capacity, commissioning year, country; federal state for plants in Germany; decommissioning year for closed units; operator for units that are not closed |
| `inconsistent.sql` | net above gross capacity, non-positive capacity, decommissioned before commissioned, commissioning after the data date, in operation with a decommissioning year, renewable flag against energy carrier, ids with hidden whitespace in any of the files |
| `duplicates.sql` | the same id twice, or different ids with the same operator, name, capacity and commissioning year (compared NULL-safely) |
| `cross_source.sql` | the files disagree: an expected addition shown as closed or in reserve, an expected closure already closed, not in the main list, or listed under another id, a unit both added and closed |
| `vocabulary.sql` | energy carriers, statuses, renewable flags or record types not in the reference lists, so a new or misspelled value cannot make a rule silently pass |

Example, from `cross_source.sql`:

```sql
SELECT c.unit_id, c.operator, c.name, NULL, 'unit_id',
       'expected closure not found in the main list, by id or by name', c.mw || ' MW, ' || c.place
  FROM closures c
 WHERE c.unit_id IS NOT NULL
   AND c.unit_id NOT IN (SELECT unit_id FROM plants WHERE unit_id IS NOT NULL)
   AND lower(trim(c.name)) NOT IN (SELECT lower(trim(name)) FROM plants WHERE name IS NOT NULL)
```

The `IS NOT NULL` inside the subqueries matters: `x NOT IN (...)` is never true when the subquery
returns a NULL.

## Run it

    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    python -m ppcheck              # downloads the two files to data/raw/, runs the checks, writes results/
    python -m ppcheck --refresh    # download the files again first
    pytest

The data is loaded into an in-memory SQLite database; the only dependency is `openpyxl` for the
Excel file. The Bundesnetzagentur updates the files regularly, so a later download can give
different results; compare its checksums with `results/source.json`. If the layout changes (a CSV
column or the sheet renamed, the Excel columns reordered, no data date), the loader stops with an
error instead of producing wrong results.

`tests/` has a case that must be flagged for every rule (and cases that must not be, such as
plants abroad without a federal state or the aggregate rows), plus tests for the parsing: decimal
commas, the title lines above the header, the two tables on one sheet, rows without an id, ids
with whitespace, and a changed layout.

## How it was built

I set the goal: a data-quality tool on public German energy data that I could show in an
application. An AI coding assistant (Claude Code) chose the data source and wrote the code and
this README. Every finding in the results table was checked against the raw file (the CSV line or
the Excel cell); of the duplicate groups, HKW III Block B and Datteln were checked. A second AI
model reviewed the project twice; the bugs it found are fixed in the commit history.

## Data and licence

Data: Bundesnetzagentur, Kraftwerksliste and "Zu- und Rückbau", Datenstand 26.06.2026, from
https://www.bundesnetzagentur.de (source: Marktstammdatenregister). The raw files are not in this
repository; `python -m ppcheck` downloads them. A third-party dataset states the licence as
Datenlizenz Deutschland – Namensnennung 2.0; I did not find the licence on the Bundesnetzagentur
page itself. `results/` contains a few records derived from these files.

Code: MIT, see `LICENSE`.

## Limitations

- The rules were written for this project from the published file. Someone who works with the
  Marktstammdatenregister would add others, for example capacity ranges per technology or
  location checks.
- Duplicate detection is exact after lowercasing and trimming; names that differ in spelling or
  spacing are not matched. Name matching across the files is exact in the same way.
- The decommissioning year follows the file's footnote: units closed on 31 December are counted
  in the following year. A rule comparing years can be off by one around the turn of a year.
- The checks run on one snapshot and do not track changes between releases.
