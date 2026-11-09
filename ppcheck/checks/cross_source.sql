-- Outdated or conflicting between the two BNetzA files. For each case at least one of the two
-- is out of date for that unit, or the unit needs a closer look.
SELECT 'cross_source' AS check_name, mastr_id, operator, name, field, issue FROM (
    -- an expected addition (in construction or test operation) that the main list shows as
    -- decommissioned or in reserve
    SELECT a.mastr_id, p.operator, p.name, 'status' AS field,
           'expected addition, but main list status is: ' || p.status AS issue
      FROM additions a JOIN plants p ON p.mastr_id = a.mastr_id
     WHERE p.status <> 'InBetrieb'
    UNION ALL
    -- an expected closure (2026-2029) that the main list already shows as permanently closed
    SELECT c.mastr_id, p.operator, p.name, 'status',
           'expected closure, but already permanently decommissioned in the main list'
      FROM closures c JOIN plants p ON p.mastr_id = c.mastr_id
     WHERE p.status LIKE 'endgültig stillgelegt%'
    UNION ALL
    -- an expected closure that is not in the main list at all
    SELECT c.mastr_id, c.operator, c.name, 'mastr_id', 'expected closure not found in the main list'
      FROM closures c WHERE c.mastr_id NOT IN (SELECT mastr_id FROM plants WHERE mastr_id IS NOT NULL)
    UNION ALL
    -- a unit listed both as an expected addition and as an expected closure
    SELECT a.mastr_id, a.operator, a.name, 'mastr_id', 'listed as expected addition and as expected closure'
      FROM additions a JOIN closures c ON c.mastr_id = a.mastr_id
)
ORDER BY issue, mastr_id;
