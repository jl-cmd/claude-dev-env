-- Total blocks grouped by hook category, all history.
SELECT
    hook_category,
    COUNT(*) AS block_count,
    COUNT(DISTINCT hook_name) AS distinct_hook_count,
    COUNT(DISTINCT session_id) AS distinct_session_count
FROM hook_events
WHERE outcome = 'blocked'
GROUP BY hook_category
ORDER BY block_count DESC;
