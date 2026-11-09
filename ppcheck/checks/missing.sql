-- Missing values in unit records (is_unit = 1: rows with an id or a name; rows with neither are
-- aggregates of small units and are not checked).
-- Not required: a German federal state for plants abroad, and an operator for permanently
-- closed units (the list publishes those without operator).
SELECT 'missing' AS check_name, p.unit_id, p.operator, p.name, p.status, x.field, x.issue,
       x.detail
  FROM plants p
  JOIN (
    SELECT rowid AS rid, 'unit_id' AS field, 'no unit id' AS issue, NULL AS detail
      FROM plants WHERE is_unit = 1 AND unit_id IS NULL
    UNION ALL SELECT rowid, 'name', 'no name', NULL FROM plants WHERE is_unit = 1 AND name IS NULL
    UNION ALL SELECT rowid, 'status', 'no status', NULL FROM plants WHERE is_unit = 1 AND status IS NULL
    UNION ALL SELECT rowid, 'energy_carrier', 'no energy carrier', NULL
      FROM plants WHERE is_unit = 1 AND energy_carrier IS NULL
    UNION ALL SELECT rowid, 'net_mw', 'no net capacity', NULL
      FROM plants WHERE is_unit = 1 AND net_mw IS NULL
    UNION ALL SELECT rowid, 'gross_mw', 'no gross capacity', NULL
      FROM plants WHERE is_unit = 1 AND gross_mw IS NULL
    UNION ALL SELECT rowid, 'year_commissioned', 'no commissioning year',
           'decommissioned in ' || year_decommissioned
      FROM plants WHERE is_unit = 1 AND year_commissioned IS NULL
    UNION ALL SELECT rowid, 'country', 'no country', NULL
      FROM plants WHERE is_unit = 1 AND country IS NULL
    UNION ALL SELECT rowid, 'state', 'plant in Germany without federal state', NULL
      FROM plants WHERE is_unit = 1 AND state IS NULL AND country = 'Deutschland'
    UNION ALL SELECT p.rowid, 'operator', 'no operator', NULL
      FROM plants p LEFT JOIN statuses s ON s.status = p.status
     WHERE p.is_unit = 1 AND p.operator IS NULL AND s.kind IS NOT 'closed'
    UNION ALL SELECT p.rowid, 'year_decommissioned',
           'permanently closed but no decommissioning year', NULL
      FROM plants p JOIN statuses s ON s.status = p.status
     WHERE p.is_unit = 1 AND s.kind = 'closed' AND p.year_decommissioned IS NULL
  ) x ON x.rid = p.rowid
 ORDER BY x.field, p.unit_id;
