# hooks/diagnostic/migrations

SQL migration files for the `hook_events` Neon schema. Each file applies a schema change to the `hook_events` table or its indexes.

## Files

| File | What it does |
|---|---|
| `2026-04-25-drop-themes-hook-events.sql` | Drops the `themes` hook-events table variant |
| `README.md` | Notes on the migration approach |

## Conventions

- Run migrations manually against the Neon database using `psql` or the Neon console.
- The baseline schema lives in `diagnostic/schema.sql`.
- File names follow `YYYY-MM-DD-<description>.sql` for chronological ordering.
