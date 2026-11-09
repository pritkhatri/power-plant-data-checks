-- The main list and the lists of expected additions and closures disagree. In each case at
-- least one of the files is out of date for that unit, or the unit needs a closer look.
-- Units are matched by id; an unmatched closure is also looked up by name.
SELECT 'cross_source' AS check_name, unit_id, operator, name, status, field, issue, detail FROM (
    SELECT a.unit_id, a.operator, a.name, p.status, 'status' AS field,
           'expected addition, but the main list shows it closed, closing, in reserve or with unknown status' AS issue,
           'expected start ' || a.expected_year AS detail
      FROM additions a JOIN plants p ON p.unit_id = a.unit_id
      LEFT JOIN statuses s ON s.status = p.status
     WHERE s.kind IS NULL OR s.kind IN ('reserve', 'temporarily closed', 'closing', 'closed')
    UNION ALL
    SELECT c.unit_id, c.operator, c.name, p.status, 'status',
           'expected closure, but already permanently closed in the main list',
           'closed in ' || p.year_decommissioned
      FROM closures c JOIN plants p ON p.unit_id = c.unit_id
      JOIN statuses s ON s.status = p.status
     WHERE s.kind = 'closed'
    UNION ALL
    SELECT c.unit_id, c.operator, c.name, NULL, 'unit_id',
           'expected closure not found in the main list, by id or by name',
           c.mw || ' MW, ' || c.place
      FROM closures c
     WHERE c.unit_id IS NOT NULL
       AND c.unit_id NOT IN (SELECT unit_id FROM plants WHERE unit_id IS NOT NULL)
       AND (c.name IS NULL
            OR lower(trim(c.name)) NOT IN (SELECT lower(trim(name)) FROM plants WHERE name IS NOT NULL))
    UNION ALL
    SELECT c.unit_id, c.operator, c.name, p.status, 'unit_id',
           'expected closure listed in the main list under a different id',
           'main list id ' || p.unit_id
      FROM closures c JOIN plants p ON lower(trim(p.name)) = lower(trim(c.name))
       -- a bare name like "Heizkraftwerk" is not enough: the operators must not contradict
       AND (p.operator IS NULL OR c.operator IS NULL
            OR lower(trim(p.operator)) = lower(trim(c.operator)))
     WHERE c.unit_id IS NOT NULL
       AND c.unit_id NOT IN (SELECT unit_id FROM plants WHERE unit_id IS NOT NULL)
    UNION ALL
    SELECT a.unit_id, a.operator, a.name, NULL, 'unit_id',
           'listed as expected addition and as expected closure', NULL
      FROM additions a JOIN closures c ON c.unit_id = a.unit_id
)
ORDER BY issue, unit_id;
