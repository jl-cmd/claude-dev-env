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
| `hook_log_extractor.py` | Disabled CLI: exits 0 without reading transcripts or rewriting offset state; body remains for a re-enable path that ingests `hook_*` attachments into Neon |
| `hook_log_stop_wrapper.py` | Disabled Stop wrapper stub: exits 0; not on the Stop dispatcher roster |
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

- Extractor and Stop wrapper mains are disabled and exit 0 with no work.
- Constants for the extractor (table name, offset state file, timeout) live in `hooks_constants/hook_log_extractor_constants.py`.
- Tests run with `python -m pytest diagnostic/test_hook_log_*.py`.

## Schema init

Run `hook_log_init.py` once per machine, or after rotating the Neon project.

Prerequisites: Bitwarden Secrets Manager CLI (`bws`) on PATH; a machine-account
token in `BWS_ACCESS_TOKEN` for the user environment (`setx` on Windows, shell
profile on macOS/Linux); Neon connection string stored as
`NEON_HOOK_LOGS_DATABASE_URL`; Python deps from `requirements-hook-logs.txt`.

```
bws run -- python packages/claude-dev-env/hooks/diagnostic/hook_log_init.py
```

`bws run` strips `BWS_ACCESS_TOKEN` from the child environment so the Python
process never sees it. The script verifies `NEON_HOOK_LOGS_DATABASE_URL`,
connects with a 5-second timeout, applies `schema.sql` with idempotent DDL,
runs a sentinel insert/select/delete round-trip, and prints the Neon host,
table name, and row count.

## Operator CLI flags

`hook_log_extractor.py` and `hook_log_stop_wrapper.py` mains exit 0 with no work.
The extractor body still documents these flags for a re-enable path:

- default / `--incremental`: resume from `~/.claude/logs/hooks/.state/offsets.json`
- `--full-rebuild`: clear offsets, truncate `hook_events`, re-read every JSONL
- `--summary`: print the top-10 blockers of the last 24 hours
- `--query <name>`: run `queries/<name>.sql` (`top_blockers_overall`,
  `top_blockers_last_24_hours`, `blocks_last_7_days`, `blocks_by_category`,
  `blocks_by_tool`, `block_details_for_hook`)

