-- Missing values in unit records (rows with a MaStR id). Rows without an id are aggregates
-- (small units summed per state and energy carrier) and are not checked.
-- Plants abroad legitimately have no German federal state. Decommissioned units are published
-- without operator, so the operator is only required for units that are not decommissioned.
SELECT 'missing' AS check_name, mastr_id, operator, name, field, issue FROM (
    SELECT mastr_id, operator, name, 'operator' AS field, 'no operator' AS issue
      FROM plants
     WHERE mastr_id IS NOT NULL AND operator IS NULL AND status NOT LIKE 'endgültig stillgelegt%'
    UNION ALL
    SELECT mastr_id, operator, name, 'name', 'no name'
      FROM plants WHERE mastr_id IS NOT NULL AND name IS NULL
    UNION ALL
    SELECT mastr_id, operator, name, 'net_mw', 'no net capacity'
      FROM plants WHERE mastr_id IS NOT NULL AND net_mw IS NULL
    UNION ALL
    SELECT mastr_id, operator, name, 'year_commissioned', 'no commissioning year'
      FROM plants WHERE mastr_id IS NOT NULL AND year_commissioned IS NULL
    UNION ALL
    SELECT mastr_id, operator, name, 'state', 'plant in Germany without federal state'
      FROM plants WHERE mastr_id IS NOT NULL AND state IS NULL AND country = 'Deutschland'
    UNION ALL
    SELECT mastr_id, operator, name, 'year_decommissioned',
           'permanently decommissioned but no decommissioning year'
      FROM plants
     WHERE mastr_id IS NOT NULL AND status LIKE 'endgültig stillgelegt%'
       AND year_decommissioned IS NULL
)
ORDER BY field, mastr_id;
