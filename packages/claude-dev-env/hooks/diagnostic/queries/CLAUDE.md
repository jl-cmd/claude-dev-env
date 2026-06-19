# hooks/diagnostic/queries

Parameterized SQL queries for inspecting the `hook_events` Neon table. Run these directly against the Neon database to analyze hook-firing patterns.

## Files

| File | What it returns |
|---|---|
| `block_details_for_hook.sql` | Full details for all blocked events matching a given hook name |
| `blocks_by_category.sql` | Count of blocks grouped by hook category |
| `blocks_by_tool.sql` | Count of blocks grouped by tool name |
| `blocks_last_7_days.sql` | All blocked events from the last 7 days |
| `top_blockers_last_24_hours.sql` | Hook names with the most blocks in the last 24 hours |
| `top_blockers_overall.sql` | Hook names with the most blocks across all time |

## Conventions

- Queries target the `hook_events` table and `blocked_commands` view defined in `diagnostic/schema.sql`.
- Run with `psql $DATABASE_URL -f <query>.sql` or paste into the Neon console.
