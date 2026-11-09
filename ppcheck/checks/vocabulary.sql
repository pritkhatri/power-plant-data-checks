-- Values outside the known vocabulary (reference tables in load.py). A new or misspelled value
-- would otherwise make the rule-based checks silently report "clean".
SELECT 'vocabulary' AS check_name, unit_id, operator, name, status, field, issue, detail FROM (
    SELECT unit_id, operator, name, status, 'energy_carrier' AS field,
           'unknown energy carrier' AS issue, energy_carrier AS detail
      FROM plants
     WHERE energy_carrier IS NOT NULL AND energy_carrier NOT IN (SELECT energy_carrier FROM carriers)
    UNION ALL
    SELECT unit_id, operator, name, status, 'status', 'unknown status', status
      FROM plants WHERE status IS NOT NULL AND status NOT IN (SELECT status FROM statuses)
    UNION ALL
    SELECT unit_id, operator, name, status, 'renewable', 'renewable flag not Ja/Nein', renewable
      FROM plants WHERE renewable IS NOT NULL AND renewable NOT IN ('Ja', 'Nein')
    UNION ALL
    SELECT unit_id, operator, name, status, 'record_type', 'unknown record type', record_type
      FROM plants
     WHERE is_unit = 1 AND COALESCE(record_type, '') NOT IN (SELECT record_type FROM record_types)
)
ORDER BY field, unit_id;
