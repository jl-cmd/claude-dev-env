---
description: Extract hook-firing records from session transcripts into Neon and show blocker summary
allowed-tools: Bash
---

Scan every JSONL session transcript under `~/.claude/projects/` (or the
path set by the `CLAUDE_HOME` env var) and ingest `attachment` records
whose inner `type` is one of the five enumerated variants in
`OUTCOME_BY_ATTACHMENT_TYPE` (`hook_success`, `hook_blocking_error`,
`hook_non_blocking_error`, `hook_system_message`,
`hook_additional_context`). Each ingested record becomes one row in
the Neon `hook_events` table. Unknown `hook_`-prefixed variants are
skipped until `OUTCOME_BY_ATTACHMENT_TYPE` is extended to cover them.
The Stop hook runs this on every session end using the `--incremental`
flag.

## Run modes

```
bws run -- python packages/claude-dev-env/hooks/diagnostic/hook_log_extractor.py
```

Full extraction using the current byte offsets in
`~/.claude/logs/hooks/.state/offsets.json` (override the `~/.claude`
root by setting `CLAUDE_HOME`). Equivalent to the Stop hook's
`--incremental` invocation; passing `--incremental` explicitly is a
documented no-op that selects the same default resumption path.

```
bws run -- python packages/claude-dev-env/hooks/diagnostic/hook_log_extractor.py --full-rebuild
```

Clear offsets, truncate `hook_events`, and re-read every JSONL from byte
zero. Use this after a schema migration or when the offsets file is
suspected of drift.

```
bws run -- python packages/claude-dev-env/hooks/diagnostic/hook_log_extractor.py --summary
```

Skip extraction. Print the top-10 blockers of the last 24 hours with
their block count and a single truncated command preview, or
`No new blocks since last run.` when the window is empty.

```
bws run -- python packages/claude-dev-env/hooks/diagnostic/hook_log_extractor.py --query <name>
```

Run the pre-baked query `queries/<name>.sql` and print the result as an
aligned text table. Available query names match the SQL files in
`packages/claude-dev-env/hooks/diagnostic/queries/`:

- `top_blockers_overall`
- `top_blockers_last_24_hours`
- `blocks_last_7_days`
- `blocks_by_category`
- `blocks_by_tool`
- `block_details_for_hook`

## Offline behavior

If the psycopg connection fails with `OperationalError`, the
5-second timeout elapses, `NEON_HOOK_LOGS_DATABASE_URL` is unset, or
the `psycopg` driver is not installed, the extractor appends one
ISO-8601 line to `~/.claude/logs/hook-extractor.log` (override the
`~/.claude` root with the `CLAUDE_HOME` env var) and exits with
status 0. Session shutdown stays fast, and the next online run
backfills from the existing offsets. The warning line records only
the timestamp and the exception class name so connection URLs never
leak into the log.
