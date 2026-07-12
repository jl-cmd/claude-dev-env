# State across ticks

**Dual persistence:** Single-PR `/pr-converge` writes loop state to
`$CLAUDE_JOB_DIR/pr-converge-state.json`; that file is the source of truth
for `phase`, heads, counters, status. Multi-PR mode additionally maintains
`<TMPDIR>/pr-converge-<session_id>/state.json` for orchestrator coordination
across PRs. Both files share most of the fields below; the
`bugteam_skill_invoked_at_head` and `bugteam_skill_invoked_at_tick` fields
live ONLY in the single-PR `$CLAUDE_JOB_DIR/pr-converge-state.json` file
(see those field entries below for details).

- `phase`: `BUGBOT`, `CODE_REVIEW`, `BUGTEAM`, or `COPILOT_WAIT`. Start
  `CODE_REVIEW` on first tick. `BUGBOT` is the terminal external-confirmation
  phase reached after BUGTEAM converges; the internal `CODE_REVIEW` and
  `BUGTEAM` passes drive the code to clean before it runs.
- `bugbot_clean_at`: HEAD SHA where bugbot last reported clean, or `null`.
  Reset to `null` on every push.
- `code_review_clean_at`: HEAD SHA where the `/code-review` pass last
  reported clean (no validated findings), or `null`. Reset to `null` on
  every push.
- `bugteam_clean_at`: HEAD SHA where bugteam last reported clean, or `null`.
  Reset to `null` on every push.
- `copilot_clean_at`: HEAD SHA where Copilot last reported clean, or `null`.
  Reset to `null` on every push.
- `merge_state_status`: last-observed `mergeable_state` from
  `pull_request_read(method="get")` (e.g. `clean`, `dirty`, `blocked`,
  `behind`, `unknown`, `unstable`), or `null` before the first check. Reset
  to `null` on every push. Gate (c) in [convergence-gates.md](convergence-gates.md)
  invokes rebase on `dirty`; other non-`clean` values (`blocked`, `behind`,
  `unknown`, `unstable`) are hard blockers.
- `current_head`: SHA of the last-known PR HEAD. Each tick refreshes it from
  `pull_request_read(method="get")` → `.head.sha`, and again after any push
  that moves HEAD. Clean-at stamps, wait counters, and phase gates compare
  against this value.
- `copilot_wait_count`: integer, init `0`. Consecutive COPILOT_WAIT ticks
  with no Copilot review surfaced at `current_head`. Escalate as hard blocker
  at `>= 3`. Reset to `0` when a Copilot review surfaces at `current_head`
  (APPROVED or dirty) or on any non-COPILOT_WAIT branch.
- `copilot_down`: boolean, init `false`. Set `true` at the start of the run
  when the Copilot quota pre-check
  (`_shared/pr-loop/scripts/copilot_quota.py`) exits non-zero — the account is
  out of premium-request quota, the quota API or account access is down, or no
  account is set. Read once from the start-of-run pre-check, not re-queried per
  tick. While `true`, every tick skips the Copilot gate outright (no fetch, no
  request, no poll, no agent) and exports `CLAUDE_REVIEWS_DISABLED="copilot"`
  before the convergence check, so `check_convergence.py` bypasses the Copilot
  review gate and the pending-requested-reviews gate and the run marks ready on
  the remaining signals. Unlike `bugbot_down`, it is not reset on push — a
  quota outage holds for the whole run.
- `inline_lag_streak`: integer, init `0`. Consecutive ticks where review
  body shows findings against `current_head` but inline API returns zero
  matching. Reset to `0` on any other branch outcome.
- `bugbot_down`: boolean, init `false`. Set `true` when bugbot fails to
  acknowledge a trigger comment; the convergence gates then run with the Bugbot
  gate bypassed. Also set `true` at the terminal BUGBOT-phase entry whenever the
  availability gate reports Bugbot disabled for the run — the default unless
  `CLAUDE_REVIEWS_ENABLED` lists the `bugbot` token, and always when
  `CLAUDE_REVIEWS_DISABLED` lists it (the BUGBOT entry gate in `per-tick.md`),
  which advances to the convergence gates before any bugbot fetch or trigger.
  Also set `true` when an acknowledged trigger has been outstanding more than 30
  minutes with no surfaced review at `current_head` (per the terminal BUGBOT gate
  30-minute budget — see `per-tick.md`). Reset to `false` on every push; the
  entry gate re-applies the availability check on the next BUGBOT entry.
  Once set, remains `true` until the next push; if bugbot stays down
  across ticks, the flag persists and the convergence gates keep the Bugbot gate
  bypassed.
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
- `agents_session_id`: string or `null`, init `null`. The session id that
  spawned the persistent per-step agents recorded in `persistent_agents`.
  On tick entry, compare it to the current session id: when they differ,
  clear `persistent_agents` to `{}` and stamp this field with the current
  session id. `ScheduleWakeup` re-enters the same session, so a mismatch
  means a fresh-session manual resume — the stored agent ids point at dead
  agents and must not be reused.
- `persistent_agents`: object, init `{}`. Map of step-key →
  `{agent_id, created_tick, last_used_tick}` for the persistent per-step
  agents the loop resumes across ticks. Exactly three step keys:
  `fix_executor` (the clean-coder that applies findings in Step 4 dirty,
  Step 6 findings, gates (a)/(b)/(e), and Step 7a), `thread_sweep`, and
  `copilot_watch`. `agent_id` is the id the `Agent` tool returned at spawn;
  `created_tick` is the `tick_count` at spawn; `last_used_tick` is bumped
  on every `SendMessage` resume.

Single-PR tick begins by reading `$CLAUDE_JOB_DIR/pr-converge-state.json`
if it exists and ends by writing the updated state back to that same file
before scheduling the next wakeup. Multi-PR mode additionally coordinates
across PRs via `<TMPDIR>/pr-converge-<session_id>/state.json` per
`multi-pr-orchestration.md` §What orchestrator does per tick.

## Handoff files

Each tick also writes a durable handoff under
`~/.claude/runtime/pr-loop/<run-name>/` via
`skills/_shared/pr-loop/scripts/write_handoff.py`: `handoff.json` (resume
command, phase, tick, and state path), `HANDOFF.md` (a prompt a fresh session
reads), and `state-copy.json` (a copy of the job-dir state). `$CLAUDE_JOB_DIR`
can be cleaned between sessions; this directory under the user home is not, so it
holds the pointer a new job needs. Live job-dir state wins for a resumed tick. A
fresh session reads the handoff copy only when `$CLAUDE_JOB_DIR` state is gone,
seeding phase, tick, and SHAs from `state-copy.json`.
