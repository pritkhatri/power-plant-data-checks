# power-plant-data-checks

Data-quality checks in plain SQL on the Bundesnetzagentur power plant list (Kraftwerksliste)
and its list of expected additions and closures. The checks look for missing, inconsistent,
duplicate and outdated records and write a work list (CSV) with one row per finding, so someone
can go through it and fix or confirm each record.

## Results

Run on the data published with Datenstand 26.06.2026. The list has 2,614 rows. 2,169 of them
are unit records with a MaStR id; the rest are aggregates (small units summed per federal state
and energy carrier) and are not checked. The change lists hold 27 expected additions and 40
expected closures.

| check | finding | rows |
|---|---|---|
| missing | decommissioned unit without commissioning year | 1 |
| inconsistent | net capacity above gross capacity (Datteln: 113 MW net, 95 MW gross) | 1 |
| inconsistent | MaStR id with a leading tab character in the list of expected additions | 1 |
| duplicate | same operator, name, capacity and commissioning year as another unit | 13 (4 groups) |
| cross-source | expected closure (Stuttgart-Münster GT 18) not found in the main list | 1 |

The full list is in `results/worklist.csv`, the counts in `results/summary.md`.

What these numbers mean:

- The official list is clean in most respects. No missing values in the active units, no
  duplicate ids, no renewable flag that contradicts the energy carrier, no unit commissioned
  after the data date. The findings are few and specific.
- A flag is a reason to look, not proof of an error. Two identical units at one site can be
  real (one duplicate group is five units of the same size at one ENGIE site).
- 238 permanently decommissioned units are published without an operator. The checks do not flag
  them, because this looks like a deliberate publication choice.
- The id with a tab character is the kind of error that hides: a plain join on the id silently
  drops that unit. The loader strips whitespace, and the check reports where it had to.

## The checks

Each check is one SQL file in `ppcheck/checks/` and returns the same columns
(`check_name, mastr_id, operator, name, field, issue`).

| file | what it looks for |
|---|---|
| `missing.sql` | empty required fields: name, capacity, commissioning year, federal state (only for plants in Germany), decommissioning year for decommissioned units, operator for units that are not decommissioned |
| `inconsistent.sql` | fields that contradict each other: net above gross capacity, non-positive capacity, decommissioned before commissioned, commissioning after the data date, "in operation" with a decommissioning year, renewable flag against energy carrier, ids with hidden whitespace |
| `duplicates.sql` | the same id twice, or different ids with the same operator, name, capacity and commissioning year |
| `cross_source.sql` | the main list and the change lists disagree: an expected addition that is decommissioned or in reserve, an expected closure that is already closed or missing from the main list, a unit listed as both addition and closure |

Example, from `cross_source.sql`:

```sql
SELECT c.mastr_id, c.operator, c.name, 'mastr_id', 'expected closure not found in the main list'
  FROM closures c
 WHERE c.mastr_id NOT IN (SELECT mastr_id FROM plants WHERE mastr_id IS NOT NULL)
```

## Run it

    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    python -m ppcheck      # downloads the two files to data/raw/, runs the checks, writes results/
    pytest

The data is loaded into an in-memory SQLite database; the only dependency is `openpyxl` for the
Excel file. `data/raw/SOURCE.json` records the download URLs and SHA-256 checksums. The
Bundesnetzagentur updates the files regularly, so a later download can give different results.

`tests/` has one test per check on a small synthetic table with known defects, plus tests for the
CSV and Excel parsing (decimal commas, the title lines above the header, the two tables on one
sheet, ids with whitespace).

## Data and licence

Data: Bundesnetzagentur, Kraftwerksliste and "Zu- und Rückbau", Datenstand 26.06.2026, from
https://www.bundesnetzagentur.de (source: Marktstammdatenregister). The raw files are not in this
repository; `python -m ppcheck` downloads them. A third-party dataset states the licence as
Datenlizenz Deutschland – Namensnennung 2.0; I did not find the licence on the Bundesnetzagentur
page itself. `results/` contains a few records derived from these files.

Code: MIT, see `LICENSE`.

## Limitations

- The rules are mine. Someone who works with the Marktstammdatenregister would add others (for
  example plausibility of capacity per technology, or location checks).
- Duplicate detection is exact after lowercasing and trimming. Names that differ only in spelling
  or spacing are not matched.
- The checks run on one snapshot. They do not track how records change between releases.
