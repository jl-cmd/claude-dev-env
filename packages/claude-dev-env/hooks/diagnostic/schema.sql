CREATE TABLE IF NOT EXISTS hook_events (
    id BIGSERIAL PRIMARY KEY,
    event_timestamp TIMESTAMPTZ NOT NULL,
    session_id TEXT NOT NULL,
    cwd TEXT,
    git_branch TEXT,
    hook_event TEXT NOT NULL,
    hook_name TEXT NOT NULL,
    hook_category TEXT NOT NULL,
    script_path TEXT,
    tool_name TEXT,
    tool_use_id TEXT,
    outcome TEXT NOT NULL,
    exit_code INTEGER,
    duration_ms INTEGER,
    command_excerpt TEXT,
    stdout_excerpt TEXT,
    stderr_excerpt TEXT,
    source_jsonl_path TEXT NOT NULL,
    source_line_number INTEGER NOT NULL,
    CONSTRAINT hook_events_source_location_unique UNIQUE (source_jsonl_path, source_line_number)
);

CREATE INDEX IF NOT EXISTS idx_hook_events_category_outcome ON hook_events (hook_category, outcome);
CREATE INDEX IF NOT EXISTS idx_hook_events_timestamp ON hook_events (event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_hook_events_hook_name ON hook_events (hook_name);
CREATE INDEX IF NOT EXISTS idx_hook_events_session ON hook_events (session_id);

CREATE OR REPLACE VIEW blocked_commands AS
SELECT
    id,
    event_timestamp,
    session_id,
    cwd,
    git_branch,
    hook_event,
    hook_name,
    hook_category,
    script_path,
    tool_name,
    tool_use_id,
    outcome,
    exit_code,
    duration_ms,
    command_excerpt,
    stdout_excerpt,
    stderr_excerpt,
    source_jsonl_path,
    source_line_number
FROM hook_events
WHERE outcome = 'blocked';
