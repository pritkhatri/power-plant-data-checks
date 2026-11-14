Data date (Datenstand): 26.06.2026.

- Power plant list: 2614 rows, of which 2169 are unit records (an id or a name). The other rows have neither and are treated as aggregates (Kleinanlagen_aggregiert: 290, stillgelegte Anlagen: 154, (no record type): 1); the unit rules do not apply to them, the vocabulary check does. 117 unit ids are older BNA numbers (117 of them on permanently closed units), the rest MaStR numbers.
- Expected additions: 37, of which 10 have no id yet and 26 have an id that is not in the main list (normal for units still being built).
- Expected closures: 40, of which 0 have no id.
- Operator: 238 of 266 permanently closed units have none (117 with a BNA id, 121 of 149 with a MaStR id); units that are not closed lacking one: 0. The operator is therefore only required for units that are not closed.
- The vocabulary check compares against reference lists built from this snapshot, so it guards later downloads; on this snapshot it can only flag rows outside the record types.

| check | issue | rows |
|---|---|---|
| missing | no commissioning year | 1 |
| inconsistent | id in the list of expected additions has whitespace | 1 |
| inconsistent | id in the main list has whitespace | 1 |
| inconsistent | net capacity above gross capacity | 1 |
| duplicates | same operator, name, capacity and year as another unit | 28 |
| cross_source | expected closure not found in the main list, by id or by name | 1 |
| vocabulary | missing or unknown record type | 1 |
| capacity_ratio | Suspiciously low net-to-gross capacity ratio | 4 |

Capacity behind the findings (net MW; see `ppcheck/impact.py` for how it is counted). For scale: all rows that are not permanently closed add up to 294,654 MW.

| check | issue | findings | MW at stake | of which not closed |
|---|---|---|---|---|
| capacity_ratio | Suspiciously low net-to-gross capacity ratio | 4 | 19.5 | 19.5 |
| cross_source | expected closure not found in the main list, by id or by name | 1 | 23.4 | 23.4 |
| duplicates | same operator, name, capacity and year as another unit | 28 | 764.5 | 120.3 |
| inconsistent | id in the list of expected additions has whitespace | 1 | 60.0 | 60.0 |
| inconsistent | id in the main list has whitespace | 1 | 297.0 | 0.0 |
| inconsistent | net capacity above gross capacity | 1 | 113.0 | 0.0 |
| missing | no commissioning year | 1 | 27.0 | 0.0 |
| vocabulary | missing or unknown record type | 1 | 1,522.8 | 1,522.8 |
