-- Daily block counts for the last 7 days, grouped by hook.
SELECT
    DATE_TRUNC('day', event_timestamp)::DATE AS block_day,
    hook_name,
    hook_category,
    COUNT(*) AS block_count
FROM hook_events
WHERE outcome = 'blocked'
    AND event_timestamp >= (NOW() - INTERVAL '7 days')
GROUP BY block_day, hook_name, hook_category
ORDER BY block_day DESC, block_count DESC;
