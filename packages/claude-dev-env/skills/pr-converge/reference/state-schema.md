# State across ticks

**Dual persistence:** Single-PR `/pr-converge` writes loop state to
`$CLAUDE_JOB_DIR/pr-converge-state.json`; that file is the source of truth
for `phase`, heads, counters, status. Multi-PR mode additionally maintains
`<TMPDIR>/pr-converge-<session_id>/state.json` for orchestrator coordination
across PRs. Both files share most of the fields below; the
`bugteam_skill_invoked_at_head` and `bugteam_skill_invoked_at_tick` fields
live ONLY in the single-PR `$CLAUDE_JOB_DIR/pr-converge-state.json` file
(see those field entries below for details).

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
- `bugteam_skill_invoked_at_head`: HEAD SHA (string) at which the formal
  `Skill({skill: "bugteam"})` was last invoked, or `null`. Stamped by the
  `pr_converge_bugteam_skill_tracker` hook on every formal bugteam Skill
  invocation. **On-disk location:** the tracker writes this field to
  `$CLAUDE_JOB_DIR/pr-converge-state.json` (single-PR mode); it is NOT
  mirrored into the multi-PR `<TMPDIR>/pr-converge-<session_id>/state.json`
  file. Operators inspecting these stamps must read the single-PR
  `pr-converge-state.json` under `$CLAUDE_JOB_DIR`. Reset by overwrite on
  the next bugteam Skill invocation; staleness is detected by the head/tick
  equality check rather than by explicit reset. The
  `pr_converge_bugteam_enforcer` hook reads this field together with
  `current_head` to confirm the formal Skill registered at the current HEAD
  before allowing follow-on clean-coder audit-shaped Agent spawns. `qbug`
  invocations deliberately do NOT update this field.
- `bugteam_skill_invoked_at_tick`: integer tick number at which the formal
  bugteam Skill was last invoked, or `null`. Companion to
  `bugteam_skill_invoked_at_head` and persisted to the same
  `$CLAUDE_JOB_DIR/pr-converge-state.json` file (single-PR mode only).
  Reset by overwrite on the next bugteam Skill invocation; staleness is
  detected by the head/tick equality check rather than by explicit reset.
  The enforcer requires this value to equal the current `tick_count` so a
  Skill invocation from a prior tick cannot wave through clean-coder
  audit-shaped Agent spawns on a later tick at the same HEAD.

Single-PR tick begins by reading `$CLAUDE_JOB_DIR/pr-converge-state.json`
if it exists and ends by writing the updated state back to that same file
before scheduling the next wakeup. Multi-PR mode additionally coordinates
across PRs via `<TMPDIR>/pr-converge-<session_id>/state.json` per
`multi-pr-orchestration.md` §What orchestrator does per tick.
