-- Inconsistent values: fields that contradict each other within one unit record, and ids in the
-- change lists that carry hidden whitespace (they silently fail a plain join).
SELECT 'inconsistent' AS check_name, mastr_id, operator, name, field, issue FROM (
    SELECT mastr_id, operator, name, 'net_mw' AS field, 'net capacity above gross capacity' AS issue
      FROM plants WHERE mastr_id IS NOT NULL AND net_mw > gross_mw
    UNION ALL
    SELECT mastr_id, operator, name, 'net_mw', 'capacity not positive'
      FROM plants WHERE mastr_id IS NOT NULL AND (net_mw <= 0 OR gross_mw <= 0)
    UNION ALL
    SELECT mastr_id, operator, name, 'year_decommissioned', 'decommissioned before commissioned'
      FROM plants WHERE year_decommissioned < year_commissioned
    UNION ALL
    SELECT mastr_id, operator, name, 'year_commissioned', 'commissioning year after the data date'
      FROM plants
     WHERE year_commissioned >
           CAST(substr((SELECT value FROM meta WHERE key = 'data_date'), -4) AS INTEGER)
    UNION ALL
    SELECT mastr_id, operator, name, 'status', 'in operation but has a decommissioning year'
      FROM plants WHERE status = 'InBetrieb' AND year_decommissioned IS NOT NULL
    UNION ALL
    SELECT mastr_id, operator, name, 'renewable', 'renewable flag does not match the energy carrier'
      FROM plants
     WHERE mastr_id IS NOT NULL
       AND ((energy_carrier IN ('Wasser', 'Biomasse', 'Wind (onshore)', 'SolareStrahlungsenergie')
             AND renewable = 'Nein')
         OR (energy_carrier IN ('Erdgas', 'Steinkohle', 'Braunkohle', 'Mineraloelprodukte')
             AND renewable = 'Ja'))
    UNION ALL
    SELECT mastr_id, operator, name, 'mastr_id', 'id in the list of expected additions has whitespace'
      FROM additions WHERE raw_id <> mastr_id
    UNION ALL
    SELECT mastr_id, operator, name, 'mastr_id', 'id in the list of expected closures has whitespace'
      FROM closures WHERE raw_id <> mastr_id
)
ORDER BY field, mastr_id;
