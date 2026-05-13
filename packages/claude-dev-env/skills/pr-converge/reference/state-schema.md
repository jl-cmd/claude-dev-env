# State across ticks

**Dual persistence:** `<TMPDIR>/pr-converge-<session_id>/state.json`
exists (multi-PR) → that file is source of truth for `phase`, heads,
counters, status, not conversation transcript. No `state.json` (typical
single-PR `/pr-converge`) → track in each assistant turn as
plain text so next tick re-reads from context:

- `phase`: `BUGBOT`, `BUGTEAM`, or `COPILOT_WAIT`. Start `BUGBOT` on first tick.
- `bugbot_clean_at`: HEAD SHA where bugbot last reported clean, or `null`.
  Reset to `null` on every push.
- `copilot_clean_at`: HEAD SHA where Copilot last reported clean, or `null`.
  Reset to `null` on every push.
- `copilot_wait_count`: integer, init `0`. Consecutive COPILOT_WAIT ticks
  with no Copilot review surfaced at `current_head`. Escalate as hard blocker
  at `>= 3`. Reset to `0` when a Copilot review surfaces at `current_head`
  (APPROVED or dirty) or on any non-COPILOT_WAIT branch.
- `inline_lag_streak`: integer, init `0`. Consecutive ticks where review
  body shows findings against `current_head` but inline API returns zero
  matching. Reset to `0` on any other branch outcome.
- `bugbot_down`: boolean, init `false`. Set `true` when bugbot fails to
  acknowledge a trigger comment; forces phase to BUGTEAM. Also set `true`
  when an acknowledged trigger has been outstanding more than 30 minutes
  with no surfaced review at `current_head` (per Step 2 BUGBOT (c)
  30-minute budget — see `per-tick.md`). Reset to `false` on every push.
  Once set, remains `true` until the next push; if bugbot stays down
  across ticks, the flag persists and BUGTEAM continues.
- `bugbot_acknowledged_at`: ISO 8601 timestamp string or `null`. Records
  the wall-clock moment Cursor Bugbot acknowledged the most recent
  `bugbot run` trigger comment (i.e. the trigger comment carries an
  `:eyes:`/`:+1:` reaction). Init `null`. Set in Step 3 once the
  reaction-check fires positive. Reset to `null` on every push and on
  every BUGTEAM jump triggered by the 30-minute budget. Step 2 BUGBOT
  (c) reads this field to decide between "schedule next wakeup" and
  "escalate to bugbot-down".
- `tick_count`: integer, init `0`. Increment every tick.

Tick begins reading prior state line from most recent assistant message
(no `state.json`) and ends by emitting updated state line; with
`state.json`, follow `multi-pr-orchestration.md` §What orchestrator does per tick.
