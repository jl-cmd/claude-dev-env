# Multi-PR orchestration model

Loaded by `pr-converge` only when `state.json` exists at
`<TMPDIR>/pr-converge-<session_id>/state.json`. Single-PR runs ignore.

## Core rule: orchestrator is traffic controller only

Orchestrator (main session) **never** reads repo source files, writes code,
audits findings, or does per-PR codebase work inline. Reads `state.json` for
traffic state, writes only narrow fields per §Orchestrator `state.json`
writes, receives teammate handoffs, spawns next worker. Every audit/fix unit
runs inside dedicated teammate.

[Workflow-style skill](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#use-workflows-for-complex-tasks):
orchestrator splits multi-PR problem into parallel per-PR subworkflows
owned by short-lived teammates. Orchestrator job: keep state file
consistent, spawn next agent.

## Per-PR state file

Create once at session start. Each teammate writes result before going idle.

**Path:** `<TMPDIR>/pr-converge-<session_id>/state.json`. **Session ID:**
`YYYYMMDDHHMMSS` captured once when loop starts.

**Directory lifecycle:** Keep `<TMPDIR>/pr-converge-<session_id>/` until every
`prs[...]` is `converged` or `blocked`, or user stops. Then delete folder.
`mark_pr_ready.py` / `gh pr ready` on GitHub is canonical record. See
[Memory](#memory) for optional append-only log.

**Barebones schema:**

```json
{
"session_id": "20260502050000",
"team_name": "bugteam-20260502050000",
"prs": {
"289": {
"owner": "jl-cmd",
"repo": "claude-code-config",
"branch": "feat/shared-pr-loop-extraction",
"phase": "BUGBOT",
"current_head": "f9a7d49e",
"bugbot_clean_at": null,
"inline_lag_streak": 0,
"tick_count": 5,
"last_action": "bugbot_triggered",
"status": "in_progress",
"last_updated": "2026-05-02T10:00:00Z"
}
}
}
```

**`team_name` field:** orchestrator owns a single long-lived team for the
whole sweep — see §Orchestrator team lifecycle.

**`status` values:** `fresh` | `in_progress` | `awaiting_bugbot` |
`awaiting_bugteam` | `converged` | `blocked`

**Write rule:** Teammates read current file, merge **only** their PR's entry
under `prs`, write back. Writes keyed on `pr_number`; other PRs untouched.

**Concurrency (mandatory):** Naive read–modify–write loses updates when
multiple teammates finish in same wall-clock window (10+ idle notifications
together). Every teammate write **must** use serialized access plus atomic
publish:

1. **Acquire** exclusive lock at sibling path `state.json.lock` via atomic
   create-only primitive (`mkdir` on Unix; on Windows `New-Item` / `md`
   guarded so only one creator succeeds, or host file lock API). On
   contention, sleep with jitter and retry. Cap retries and escalate per
   **Stop conditions** if lock never clears (stuck teammate).
2. **Read** `state.json`, merge `prs[<pr_number>]` only, write full merged
   JSON to `state.json.tmp`.
3. **Replace** `state.json` atomically from `state.json.tmp` (`os.replace` /
   same-volume rename so readers never see half-written file).
4. **Release** lock (`rmdir` / `Remove-Item`).

**Orchestrator `state.json` writes (traffic metadata only):** Teammates
own audit/fix payloads. Orchestrator **must not** merge finding bodies,
file contents, or teammate-owned fields except two exceptions. Uses same
§Concurrency lock.

1. **Per-tick `tick_count` bump (mandatory):** At start of each tick, one
   locked read–merge–publish: every `prs[<pr_number>]` whose `status` is
   not `converged` or `blocked` → increment `tick_count` by 1 (init `0`),
   refresh `last_updated`. Observability only — no ceiling; loop ends on
   convergence or **Stop conditions**.
2. **`phase` when only orchestrator decides:** Orchestrator applies a
   Step 2 phase transition (including BUGTEAM §(d) `phase = BUGBOT`
   without immediate teammate write) and no teammate merge occurs that
   tick → orchestrator performs one locked merge setting only
   `prs[<pr_number>].phase` and `last_updated`.

Orchestrator reads file at start of every tick for cross-PR state, not
conversation context.

## Orchestrator team lifecycle

**Why orchestrator owns team:** bugteam's per-invocation `TeamCreate` /
`TeamDelete` assumes one invocation per session. Multi-PR converge runs
bugteam per PR per BUGTEAM tick — many invocations. Per-call `TeamCreate`
fails with `Already leading team "<existing>"`; per-call `TeamDelete`
strands next BUGTEAM tick. Orchestrator creates one team for whole sweep,
tears down on full convergence — see [bugteam Team
lifecycle](../../bugteam/SKILL.md#team-lifecycle-path-a-only).

**At session start (before first tick):**

1. Compute `team_name = "bugteam-<session_id>"` using same `session_id` as
   §Per-PR state file.
2. `TeamCreate(team_name=<team_name>, description="pr-converge sweep
   <session_id>", agent_type="team-lead")`. Orchestrator becomes lead.
3. Locked write to `state.json` (per §Concurrency): merge `team_name` at
   document root.

**At every BUGTEAM tick (per PR):** invoke bugteam in attach mode. Set
both env vars before call:

- `BUGTEAM_TEAM_LIFECYCLE=attach`
- `BUGTEAM_TEAM_NAME=<state.team_name>`

Orchestrator driving bugteam via `Skill` sets both env vars in parent
process before `Skill` invocation. Bugteam in delegated worker (typical
multi-PR fan-out): spawn prompt exports same two env vars at top of
worker's bash environment.

**Teardown (only when every PR terminal):** every
`prs[<pr_number>].status` is `converged` or `blocked` → then only:

1. `TeamDelete()` (orchestrator is lead; no args).
2. Locked write to `state.json`: clear `team_name` from root (prevents
   stale leak into follow-up sweep).
3. §Memory cleanup of `<TMPDIR>/pr-converge-<session_id>/`.

User-stop or hard-blocker exit before convergence still calls
`TeamDelete()` (orchestrator shutting down). Only path that skips
`TeamDelete()`: "tick scheduled, sweep continuing" — common case.

## Teammate spawning rules

Multiple PRs returning simultaneously (10+ idle notifications) → spawn
one agent per PR in single parallel message. Never process any PR inline.

### Audit result → fix worker per PR

Bugfind teammate completes (findings or clean):

- **PRs with findings:** spawn one fix worker per PR
  (`clean-coder`). Worker:
  1. Reads outcomes XML.
  2. Applies TDD fixes (test first, then production).
  3. Commits, pushes one fix commit.
  4. Replies inline on each addressed finding via
     `reply_to_inline_comment.py`.
  5. Writes `state.json` (per §Concurrency): `last_action: "fix_pushed"`,
     `current_head: <new SHA>`, `bugbot_clean_at: null`, `phase:
     "BUGBOT"`, `status: "awaiting_bugbot"`, `last_updated` ISO-8601 UTC.
  6. Goes idle.

- **PRs with zero findings:** spawn one `general-purpose` agent per PR.
  Agent:
  1. `bugbot_clean_at == current_head` (back-to-back clean): run
     `mark_pr_ready.py`, append convergence row to
     `<TMPDIR>/pr-converge-<session_id>/converged.log` per §Memory, then
     write `state.json` (per §Concurrency) with `status: "converged"`,
     `last_action: "converged"` (or `marked_ready`), `phase: "BUGBOT"`,
     `last_updated` ISO-8601 UTC — **before** going idle. Skipping leaves
     orchestrator with stale `awaiting_bugteam` / `in_progress` row, risks
     duplicate work.
  2. Else: update `state.json` (per §Concurrency) with `last_action:
     "audit_clean"`, `status: "awaiting_bugbot"`, `phase: "BUGBOT"`, then
     trigger bugbot via `trigger_bugbot.py`.
  3. Goes idle.

### Fix result → general-purpose per PR

When bugfix (clean-coder) teammate goes idle after push:

- Spawn one `general-purpose` agent per PR. Agent:
  1. Reads `state.json` for its PR.
  2. Triggers bugbot via `trigger_bugbot.py`.
  3. Polls `fetch_bugbot_reviews.py` every 60s (up to 10 polls) until review
     anchored to `current_head` appears.
  4. **Poll / classify loop** (repeat from 4a whenever 4c retries):
     - **4a.** Fetch inline comments via `fetch_bugbot_inline_comments.py`.
     - **4b.** Classify — three outcomes (same as `SKILL.md` Step 2 BUGBOT):
       - **`clean`:** review body clean, zero unaddressed inline findings.
       - **`dirty`:** ≥1 unaddressed inline finding for `current_head`
         (actionable for Fix protocol / `clean-coder`).
       - **`inline_lag`:** review body shows findings, inline API returns
         zero matching for `current_head` (transient desync — `SKILL.md`
         Step 2 BUGBOT fourth bullet).
     - **4c. `inline_lag`:** locked merge: increment `inline_lag_streak`
       (missing → `0` first); set `last_action: "inline_lag_wait"`,
       `phase: "BUGBOT"`, `last_updated`; keep `status` consistent (e.g.
       `awaiting_bugbot`). `inline_lag_streak >= 3` → **hard blocker** per
       `SKILL.md` §Stop conditions (structurally inconsistent review);
       report and go idle **without** classifying as `dirty`. Else sleep
       90s and repeat from 4a (re-fetch inline only).
     - **4d. `clean`:** exit. Locked merge: `bugbot_clean_at =
       current_head`, reset `inline_lag_streak`, update `last_action`,
       `status`, `phase: BUGTEAM`.
     - **4e. `dirty`:** exit. Locked merge: reset `inline_lag_streak`,
       record findings count, update `last_action`, `status`, `phase:
       BUGBOT`.
  5. Reports one-line outcome to orchestrator.

- Orchestrator reads updated `state.json`, spawns next agent:
  - `clean` → `general-purpose` runs BUGTEAM phase (bugteam via `Skill`
    when available, else inline by reading bugteam `SKILL.md`).
  - Exited on `dirty` (4e) with actionable inline threads → spawn same
    fix worker as "audit result with findings". Do **not** spawn
    `clean-coder` when monitor only saw `inline_lag` (4c retries) without
    reaching 4e — that path retries or escalates via `inline_lag_streak ≥
    3` hard blocker, not fix pass.

## What orchestrator does per tick

1. Per-tick `tick_count` bump for every non-terminal PR under `prs`.
2. Read `state.json`.
3. Each PR with new teammate results → spawn next agent per rules, all
   in one parallel message.
4. Re-read `state.json` if needed for scheduling.
5. Call `ScheduleWakeup` with appropriate delay.
6. Nothing else.

## Memory

Run directory `<TMPDIR>/pr-converge-<session_id>/` holds `state.json` and
optional `converged.log`. Keep from first create until every PR under `prs`
is `converged` or `blocked`, or **Stop conditions** ends loop. Safe to
delete folder after — `mark_pr_ready.py` / `gh pr ready` on GitHub is
canonical record. Folder skill, not a plugin package; do **not** rely
on `${CLAUDE_PLUGIN_DATA}`. OS/disk cleanup of `<TMPDIR>` (reboot, policy)
can remove files mid-run — environmental risk.

**`converged.log` (multi-PR only — requires `state.json`):**

- **Path:** sibling of `state.json`.
- **Format:** one tab-separated row per converged PR: ISO8601 UTC,
  owner/repo#number, bugbot SHA, bugteam SHA.
- **Append site:** agent running `mark_pr_ready.py`. Append **before**
  locked `state.json` publish so log row survives failed merge.
- **Never read inside loop.** User / follow-up tooling only.

Single-PR runs without `state.json`: do **not** append `converged.log`;
in-conversation summary plus GitHub ready state suffice.
