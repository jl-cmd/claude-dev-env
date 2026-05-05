# State across ticks

**Dual persistence:** `<TMPDIR>/pr-converge-<session_id>/state.json`
exists (multi-PR) → that file is source of truth for `phase`, heads,
counters, status, not conversation transcript. No `state.json` (typical
single-PR `/pr-converge`) → track in each assistant turn as
plain text so next tick re-reads from context:

- `phase`: `BUGBOT` or `BUGTEAM`. Start `BUGBOT` on first tick.
- `bugbot_clean_at`: HEAD SHA where bugbot last reported clean, or `null`.
  Reset to `null` on every push.
- `inline_lag_streak`: integer, init `0`. Consecutive ticks where review
  body shows findings against `current_head` but inline API returns zero
  matching. Reset to `0` on any other branch outcome.
- `tick_count`: integer, init `0`. Increment every tick.

Tick begins reading prior state line from most recent assistant message
(no `state.json`) and ends by emitting updated state line; with
`state.json`, follow `multi-pr-orchestration.md` §What orchestrator does per tick.
