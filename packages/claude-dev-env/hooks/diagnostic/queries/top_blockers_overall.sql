-- Top 20 hooks by blocking count across all history.
SELECT
    hook_name,
    hook_category,
    COUNT(*) AS block_count,
    MIN(event_timestamp) AS first_block_at,
    MAX(event_timestamp) AS last_block_at
FROM hook_events
WHERE outcome = 'blocked'
GROUP BY hook_name, hook_category
ORDER BY block_count DESC
LIMIT 20;
