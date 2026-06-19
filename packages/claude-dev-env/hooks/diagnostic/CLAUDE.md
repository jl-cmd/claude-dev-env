# hooks/diagnostic

Hooks and scripts that collect, store, and query hook-firing records. The pipeline reads session JSONL transcripts, extracts hook attachment records, and writes them as rows into a Neon (Postgres) `hook_events` table.

## Subdirectories

| Directory | Role |
|---|---|
| `migrations/` | SQL migration files for the `hook_events` schema |
| `queries/` | Parameterized SQL queries for inspecting blocked commands |

## Key files

| File | What it does |
|---|---|
| `hook_log_init.py` | One-time setup: creates the Neon schema (runs `schema.sql`), then verifies read-write parity with a sentinel round-trip |
| `hook_log_extractor.py` | Stop hook — reads per-session JSONL transcripts and ingests new `hook_*` attachment records into the `hook_events` table; idempotent via a UNIQUE constraint on `(source_jsonl_path, source_line_number)` |
| `hook_log_stop_wrapper.py` | Thin wrapper that invokes `hook_log_extractor.py` from the Stop lifecycle event |
| `schema.sql` | DDL for the `hook_events` table, `blocked_commands` view, and supporting indexes |
| `requirements-hook-logs.txt` | Runtime dependencies (`psycopg`) for the extractor |
| `requirements-hook-logs-dev.txt` | Dev/test dependencies |
| `test_hook_log_extractor.py` | Tests for the extractor |
| `test_hook_log_init.py` | Tests for the schema-init script |
| `test_hook_log_stop_wrapper.py` | Tests for the Stop wrapper |

## Schema overview (`schema.sql`)

The `hook_events` table captures one row per hook firing:

- `hook_event`, `hook_name`, `hook_category` — what fired
- `outcome` — `allowed`, `blocked`, or `ask`
- `tool_name`, `command_excerpt` — what tool was called
- `session_id`, `git_branch`, `cwd` — context
- `duration_ms`, `exit_code` — timing and result
- `source_jsonl_path`, `source_line_number` — idempotency key

The `blocked_commands` view filters to `outcome = 'blocked'`.

## Conventions

- The extractor exits 0 even when Neon is unreachable (offline-graceful); it logs to `OFFLINE_WARNING_LOG` and does not block session end.
- Constants for the extractor (table name, offset state file, timeout) live in `hooks_constants/hook_log_extractor_constants.py`.
- Tests run with `python -m pytest diagnostic/test_hook_log_*.py`.
