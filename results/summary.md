Data date (Datenstand): 26.06.2026.

- Power plant list: 2614 rows, of which 2169 are unit records (an id or a name); the rest are aggregates of small units and are not checked. 117 unit ids are older BNA numbers, the rest MaStR numbers.
- Expected additions: 37, of which 10 have no id yet and 26 have an id that is not in the main list (normal for units still being built).
- Expected closures: 40, of which 0 have no id.
- Not flagged: 238 permanently closed units are published without an operator; the list appears to leave the operator out for closed units.

| check | issue | rows |
|---|---|---|
| missing | no commissioning year | 1 |
| inconsistent | id in the list of expected additions has whitespace | 1 |
| inconsistent | id in the main list has whitespace | 1 |
| inconsistent | net capacity above gross capacity | 1 |
| duplicates | same operator, name, capacity and year as another unit | 28 |
| cross_source | expected closure not found in the main list, by id or by name | 1 |
| vocabulary | (none found) | 0 |
