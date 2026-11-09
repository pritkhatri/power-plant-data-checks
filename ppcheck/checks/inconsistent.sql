-- Fields that contradict each other within one unit record, and ids published with hidden
-- whitespace (a plain join on such an id silently fails).
SELECT 'inconsistent' AS check_name, unit_id, operator, name, status, field, issue, detail FROM (
    SELECT unit_id, operator, name, status, 'net_mw' AS field,
           'net capacity above gross capacity' AS issue,
           'net ' || net_mw || ' MW, gross ' || gross_mw || ' MW'
           || COALESCE(', decommissioned in ' || year_decommissioned, '') AS detail
      FROM plants WHERE is_unit = 1 AND net_mw > gross_mw
    UNION ALL
    SELECT unit_id, operator, name, status, 'net_mw', 'capacity not positive',
           'net ' || net_mw || ' MW, gross ' || gross_mw || ' MW'
      FROM plants WHERE is_unit = 1 AND (net_mw <= 0 OR gross_mw <= 0)
    UNION ALL
    SELECT unit_id, operator, name, status, 'year_decommissioned',
           'decommissioned before commissioned',
           'commissioned ' || year_commissioned || ', decommissioned ' || year_decommissioned
      FROM plants WHERE is_unit = 1 AND year_decommissioned < year_commissioned
    UNION ALL
    SELECT unit_id, operator, name, status, 'year_commissioned',
           'commissioning year after the data date', 'commissioned ' || year_commissioned
      FROM plants
     WHERE is_unit = 1 AND year_commissioned >
           CAST(substr((SELECT value FROM meta WHERE key = 'data_date'), -4) AS INTEGER)
    UNION ALL
    SELECT p.unit_id, p.operator, p.name, p.status, 'status',
           'in operation but has a decommissioning year', 'decommissioned ' || p.year_decommissioned
      FROM plants p JOIN statuses s ON s.status = p.status
     WHERE p.is_unit = 1 AND s.kind = 'operating' AND p.year_decommissioned IS NOT NULL
    UNION ALL
    SELECT p.unit_id, p.operator, p.name, p.status, 'renewable',
           'renewable flag does not match the energy carrier',
           p.energy_carrier || ' marked renewable=' || p.renewable
      FROM plants p JOIN carriers c ON c.energy_carrier = p.energy_carrier
     WHERE p.is_unit = 1 AND c.renewable_expected IS NOT NULL
       AND p.renewable IN ('Ja', 'Nein')  -- other values are reported by vocabulary.sql
       AND p.renewable <> c.renewable_expected
    UNION ALL
    SELECT unit_id, operator, name, status, 'unit_id', 'id in the main list has whitespace',
           'published as ''' || replace(replace(raw_unit_id, char(9), '\t'), ' ', '·') || ''''
      FROM plants WHERE raw_unit_id <> unit_id
    UNION ALL
    SELECT unit_id, operator, name, NULL, 'unit_id', 'id in the list of expected additions has whitespace',
           'published as ''' || replace(replace(raw_unit_id, char(9), '\t'), ' ', '·') || ''''
      FROM additions WHERE raw_unit_id <> unit_id
    UNION ALL
    SELECT unit_id, operator, name, NULL, 'unit_id', 'id in the list of expected closures has whitespace',
           'published as ''' || replace(replace(raw_unit_id, char(9), '\t'), ' ', '·') || ''''
      FROM closures WHERE raw_unit_id <> unit_id
)
ORDER BY field, unit_id;
