-- Duplicate candidates among unit records: the same id twice, or several ids that agree on
-- operator, name, net capacity and commissioning year (compared NULL-safely with IS, so units
-- without an operator are included). The second kind can be real, identical units, so these are
-- candidates for review, not errors.
SELECT 'duplicates' AS check_name, p.unit_id, p.operator, p.name, p.status,
       'unit_id' AS field, 'id appears more than once' AS issue, d.n || ' rows' AS detail
  FROM plants p
  JOIN (SELECT unit_id, COUNT(*) AS n FROM plants
         WHERE unit_id IS NOT NULL GROUP BY unit_id HAVING n > 1) d ON d.unit_id = p.unit_id
UNION ALL
SELECT 'duplicates', p.unit_id, p.operator, p.name, p.status, 'operator+name+net_mw+year',
       'same operator, name, capacity and year as another unit',
       g.n || ' units, ' || p.net_mw || ' MW, commissioned ' || p.year_commissioned
  FROM plants p
  JOIN (SELECT lower(trim(operator)) AS o, lower(trim(name)) AS nm, net_mw, year_commissioned,
               COUNT(DISTINCT unit_id) AS n
          FROM plants WHERE is_unit = 1 AND unit_id IS NOT NULL AND name IS NOT NULL
         GROUP BY 1, 2, 3, 4 HAVING n > 1) g
    ON g.o IS lower(trim(p.operator)) AND g.nm = lower(trim(p.name))
   AND g.net_mw IS p.net_mw AND g.year_commissioned IS p.year_commissioned
 WHERE p.is_unit = 1 AND p.unit_id IS NOT NULL
ORDER BY 3, 4, 2;
