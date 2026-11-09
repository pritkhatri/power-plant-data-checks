-- Duplicate candidates among unit records: the same MaStR id twice, or several ids that agree on
-- operator, name, net capacity and commissioning year. The second kind can be real, identical
-- units (for example several identical engines), so these rows are candidates for review.
SELECT 'duplicate' AS check_name, p.mastr_id, p.operator, p.name, 'mastr_id' AS field,
       'MaStR id appears ' || d.n || ' times' AS issue
  FROM plants p
  JOIN (SELECT mastr_id, COUNT(*) AS n FROM plants
         WHERE mastr_id IS NOT NULL GROUP BY mastr_id HAVING n > 1) d
    ON d.mastr_id = p.mastr_id
UNION ALL
SELECT 'duplicate', p.mastr_id, p.operator, p.name, 'operator+name+net_mw+year',
       'same operator, name, capacity and year as another unit'
  FROM plants p
  JOIN (SELECT lower(trim(operator)) AS o, lower(trim(name)) AS nm, net_mw, year_commissioned,
               COUNT(DISTINCT mastr_id) AS n
          FROM plants WHERE mastr_id IS NOT NULL
         GROUP BY 1, 2, 3, 4 HAVING n > 1) g
    ON g.o = lower(trim(p.operator)) AND g.nm = lower(trim(p.name))
   AND g.net_mw = p.net_mw AND g.year_commissioned = p.year_commissioned
 WHERE p.mastr_id IS NOT NULL
ORDER BY 3, 4, 2;
