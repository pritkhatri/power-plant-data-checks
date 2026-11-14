-- Flag unusually low net-to-gross ratios for review, not as confirmed errors.
-- 0.5 is a conservative anomaly threshold: P5 among non-closed units is 0.817.
-- The four current findings appear to be legitimate CHP/turbine configurations.
SELECT
    'capacity_ratio' AS check_name,
    p.unit_id,
    p.operator,
    p.name,
    p.status,
    'net_mw/gross_mw' AS field,
    'Suspiciously low net-to-gross capacity ratio' AS issue,
    'net ' || CAST(p.net_mw AS VARCHAR)
        || ' MW, gross ' || CAST(p.gross_mw AS VARCHAR)
        || ' MW (ratio '
        || CAST(ROUND(p.net_mw / p.gross_mw, 3) AS VARCHAR)
        || ')' AS detail
FROM plants p
LEFT JOIN statuses s
    ON p.status = s.status
WHERE
    p.is_unit = 1
    AND s.kind IS NOT 'closed'
    AND p.net_mw IS NOT NULL
    AND p.gross_mw IS NOT NULL
    AND p.gross_mw > 0
    AND p.net_mw / p.gross_mw < 0.5
ORDER BY p.name, p.unit_id;
