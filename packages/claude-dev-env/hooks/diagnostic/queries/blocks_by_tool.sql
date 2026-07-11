-- Blocks grouped by tool name parsed from hook_name (e.g., Bash, Write, Edit).
SELECT
    COALESCE(tool_name, '(none)') AS tool_name,
    COUNT(*) AS block_count,
    COUNT(DISTINCT hook_name) AS distinct_hook_count
FROM hook_events
WHERE outcome = 'blocked'
GROUP BY tool_name
ORDER BY block_count DESC;
