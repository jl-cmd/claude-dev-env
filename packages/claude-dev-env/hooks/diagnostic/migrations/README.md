# Hook-Log Diagnostic Migrations

One-time DDL migrations for the hook-log diagnostic store. Each file is named
`YYYY-MM-DD-<short-description>.sql` and has idempotent statements that can be
re-run without error.

These files are records of operations run (or to be run) against a specific
Neon project. No hook runs them automatically.

## How to apply

A migration runs against the Postgres connection URL of the project being
modified. The runner is whichever client the operator prefers; a typical
pattern is:

```
psql "$DATABASE_URL" -f packages/claude-dev-env/hooks/diagnostic/migrations/<file>.sql
```

When the project is hosted on Neon, the `mcp__neon__run_sql_transaction` tool
accepts the same statements as a list of strings. That is the path used for
the 2026-04-25 isolation migration described below, since the operator already
has Neon MCP authenticated.

## 2026-04-25-drop-themes-hook-events.sql

**Target:** Neon project `example-project-00000000`, a production application
database. This project also held the hook-log diagnostic table up to PR #257,
because the `NEON_HOOK_LOGS_DATABASE_URL` Bitwarden secret pointed at it.

**Effect:** Drops the diagnostic view `blocked_commands` and the diagnostic
table `hook_events` from the source project. The two objects came from
`schema.sql` during a misrouted live test in session 80; they share no foreign
keys or other coupling with the project's own domain tables, and removing them
is a pure cleanup.

**State before this migration:** `hook_events` holds 10,684 rows spanning
2026-04-12 through 2026-04-24. None of these rows move; the "start fresh"
decision (recorded in PR #261) means the extractor's `--full-rebuild` mode
rebuilds the table contents from local JSONL on its next run against the
hook-log project.

**State after this migration:** the source project has only its own domain
tables. The hook-log diagnostic store lives entirely in a separate Neon project
`example-project-11111111`, which the `NEON_HOOK_LOGS_DATABASE_URL` secret
points at.

**Verification:** Before applying, confirm there is no other consumer of
`blocked_commands` or `hook_events` in the source project:

```sql
SELECT table_name, view_definition
FROM information_schema.views
WHERE table_schema = 'public'
  AND view_definition ILIKE '%hook_events%'
  AND table_name <> 'blocked_commands';

SELECT conname, conrelid::regclass
FROM pg_constraint
WHERE confrelid = 'hook_events'::regclass;
```

The first query excludes `blocked_commands` itself, since that view (also dropped by this migration) references `hook_events` in its definition and would otherwise always match.

Both queries should return zero rows; if either returns anything, investigate
the dependency before running the drop.

After applying, confirm the objects are gone:

```sql
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'public' AND table_name IN ('hook_events', 'blocked_commands');
```

Should return zero rows.
