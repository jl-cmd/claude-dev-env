-- Recent block details for the top-blocking hook in the last 30 days.
-- Shows the 25 most recent blocked attempts with the command excerpt and error
-- excerpt so diagnosis can focus on concrete failing commands rather than
-- aggregate counts. To target a specific hook, filter by hook_name in a follow-up.
WITH top_hook AS (
    SELECT hook_name
    FROM hook_events
    WHERE outcome = 'blocked'
        AND event_timestamp >= (NOW() - INTERVAL '30 days')
    GROUP BY hook_name
    ORDER BY COUNT(*) DESC
    LIMIT 1
)
SELECT
    event_timestamp,
    session_id,
    hook_event,
    hook_name,
    tool_name,
    command_excerpt,
    stderr_excerpt
FROM hook_events
WHERE outcome = 'blocked'
    AND hook_name = (SELECT hook_name FROM top_hook)
ORDER BY event_timestamp DESC
LIMIT 25;
