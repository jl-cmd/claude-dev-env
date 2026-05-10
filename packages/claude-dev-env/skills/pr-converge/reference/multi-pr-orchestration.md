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
`update_pull_request(draft=false)` on GitHub is canonical record. See
[Memory](#memory) for optional append-only log.

**Barebones schema:**

```json
{
  "session_id": "20260502050000",
  "prs": {
    "289": {
      "owner": "jl-cmd",
      "repo": "claude-code-config",
      "branch": "feat/shared-pr-loop-extraction",
      "phase": "BUGBOT",
      "current_head": "f9a7d49e",
      "bugbot_clean_at": null,
      "inline_lag_streak": 0,
      "bugbot_down": false,
      "tick_count": 5,
      "last_action": "bugbot_triggered",
      "status": "in_progress",
      "last_updated": "2026-05-02T10:00:00Z"
    }
  }
}
```

**`status` values:** `fresh` | `in_progress` | `awaiting_bugbot` |
`awaiting_bugteam` | `converged` | `blocked`

**Write rule:** Subagents read current file, merge **only** their PR's entry
under `prs`, write back. Writes keyed on `pr_number`; other PRs untouched.

**Concurrency (mandatory):** Naive read–modify–write loses updates when
multiple subagents finish in same wall-clock window (10+ idle notifications
together). Every subagent write **must** use serialized access plus atomic
publish:

1. **Acquire** exclusive lock at sibling path `state.json.lock` via atomic
   create-only primitive (`mkdir` on Unix; on Windows `New-Item` / `md`
   guarded so only one creator succeeds, or host file lock API). On
   contention, sleep with jitter and retry. Cap retries and escalate per
   **Stop conditions** if lock never clears (stuck subagent).
2. **Read** `state.json`, merge `prs[<pr_number>]` only, write full merged
   JSON to `state.json.tmp`.
3. **Replace** `state.json` atomically from `state.json.tmp` (`os.replace` /
   same-volume rename so readers never see half-written file).
4. **Release** lock (`rmdir` / `Remove-Item`).

**Orchestrator `state.json` writes (traffic metadata only):** Subagents
own audit/fix payloads. Orchestrator **must not** merge finding bodies,
file contents, or subagent-owned fields except two exceptions. Uses same
§Concurrency lock.

1. **Per-tick `tick_count` bump (mandatory):** At start of each tick, one
   locked read–merge–publish: every `prs[<pr_number>]` whose `status` is
   not `converged` or `blocked` → increment `tick_count` by 1 (init `0`),
   refresh `last_updated`. Observability only — no ceiling; loop ends on
   convergence or **Stop conditions**.
2. **`phase` when only orchestrator decides:** Orchestrator applies a
   Step 2 phase transition (including BUGTEAM §(d) `phase = BUGBOT`
   without immediate subagent write) and no subagent merge occurs that
   tick → orchestrator performs one locked merge setting only
   `prs[<pr_number>].phase` and `last_updated`.

Orchestrator reads file at start of every tick for cross-PR state, not
conversation context.

## Subagent spawning rules

Multiple PRs returning simultaneously (10+ idle notifications) → spawn
one agent per PR in single parallel message. Never process any PR inline.

### Audit result → fix worker per PR

Bugfind subagent completes (findings or clean):

- **PRs with findings:** spawn one fix worker per PR via
  `Agent(subagent_type="clean-coder", run_in_background=true)`. Worker:
  1. Reads outcomes XML.
  2. Applies TDD fixes (test first, then production).
  3. Commits, pushes one fix commit.
  4. Replies inline on each addressed finding via
     `add_reply_to_pull_request_comment(owner, repo, pullNumber, commentId, body)`.
  5. Writes `state.json` (per §Concurrency): `last_action: "fix_pushed"`,
     `current_head: <new SHA>`, `bugbot_clean_at: null`,
     `bugbot_down: false`, `phase:
     "BUGBOT"`, `status: "awaiting_bugbot"`, `last_updated` ISO-8601 UTC.
  6. Goes idle.

- **PRs with zero findings:** spawn one `general-purpose` subagent per PR via
  `Agent(subagent_type="general-purpose", run_in_background=true)`. Subagent:
  1. `bugbot_clean_at == current_head` (back-to-back clean): run the full
     four-gate flow from `convergence-gates.md`. Only when all gates
     pass — per the full gate sequence in `convergence-gates.md` — run
     `update_pull_request(pullNumber=NUMBER, owner=OWNER, repo=REPO, draft=false)`, append
     convergence row to `<TMPDIR>/pr-converge-<session_id>/converged.log`
     per §Memory, then write `state.json` (per §Concurrency) with
     `status: "converged"`, `last_action: "converged"`, `phase: "BUGBOT"`,
     `last_updated` ISO-8601 UTC — **before** going idle. Skipping leaves
     orchestrator with stale `awaiting_bugteam` / `in_progress` row, risks
     duplicate work.
  2. Else: update `state.json` (per §Concurrency) with `last_action:
     "audit_clean"`, `status: "awaiting_bugbot"`, `phase: "BUGBOT"`, then
     trigger bugbot via `add_issue_comment(owner, repo, issueNumber, body="bugbot run")`.
  3. **Bugbot-down detection.** Capture the comment ID from the
     `add_issue_comment` response. Sleep 15 seconds. Fetch comments via
     `issue_read(method="get_comments", owner=owner, repo=repo, issue_number=issue_number)`,
     select the comment whose `id` matches the captured ID, and check its
     reactions. If the comment has zero reactions (reactions
     count is `0` or absent): set `bugbot_down = true`,
     `phase: "BUGTEAM"`, `status: "in_progress"`,
     `last_action: "bugbot_down_detected"`, `last_updated` ISO-8601 UTC
     via `state.json`, spawn a `bugteam` subagent, and return (skip going
     idle). If one or more reactions present, continue to step 4.
  4. Goes idle.

### Fix result → general-purpose per PR

When bugfix (clean-coder) subagent completes after push:

- Spawn one `general-purpose` subagent per PR via
  `Agent(subagent_type="general-purpose", run_in_background=true)`. Subagent:
  1. Reads `state.json` for its PR.
  2. Triggers bugbot via `add_issue_comment(owner, repo, issueNumber, body="bugbot run")`.
  3. **Bugbot-down detection.** Capture the comment ID from the
     `add_issue_comment` response. Sleep 15 seconds. Fetch comments via
     `issue_read(method="get_comments", owner=owner, repo=repo, issue_number=issue_number)`,
     select the comment whose `id` matches the captured ID, and check its
     reactions. If the comment has zero reactions (reactions
     count is `0` or absent): set `bugbot_down = true`,
     `phase: "BUGTEAM"`, `status: "in_progress"`,
     `last_action: "bugbot_down_detected"`, `last_updated` ISO-8601 UTC
     via `state.json`, spawn a `bugteam` subagent, and return (skip
     polling loop). If one or more reactions present, continue to step 4.
  4. Polls `pull_request_read(method="get_reviews")` every 60s (up to 10 polls)
     until review anchored to `current_head` appears with `commit_id ==
     current_head`. If polling reaches limit without a matching review, write
     `state.json` with `status: "blocked"`, `last_action: "review_timeout"`,
     and go idle.
  5. **Poll / classify loop** (repeat from 5a whenever 5c retries):
     - **5a.** Fetch inline comments via `pull_request_read(method="get_review_comments")` filtered by review ID and `commit_id == current_head`.
     - **5b.** Classify — three outcomes (same as `SKILL.md` Step 2 BUGBOT):
       - **`clean`:** review body clean, zero unaddressed inline findings.
       - **`dirty`:** ≥1 unaddressed inline finding for `current_head`
         (actionable for Fix protocol / `clean-coder`).
       - **`inline_lag`:** review body shows findings, inline API returns
         zero matching for `current_head` (transient desync — `SKILL.md`
         Step 2 BUGBOT fourth bullet).
     - **5c. `inline_lag`:** locked merge: increment `inline_lag_streak`
       (missing → `0` first); set `last_action: "inline_lag_wait"`,
       `phase: "BUGBOT"`, `last_updated`; keep `status` consistent (e.g.
       `awaiting_bugbot`). `inline_lag_streak >= 3` → **hard blocker** per
       `SKILL.md` §Stop conditions (structurally inconsistent review);
       report and go idle **without** classifying as `dirty`. Else sleep
       90s and repeat from 5a (re-fetch inline only).
     - **5d. `clean`:** exit. Locked merge: `bugbot_clean_at =
       current_head`, reset `inline_lag_streak`, update `last_action`,
       `status`, `phase: BUGTEAM`.
     - **5e. `dirty`:** exit. Locked merge: reset `inline_lag_streak`,
       record findings count, update `last_action`, `status`, `phase:
       BUGBOT`.
  6. Reports one-line outcome to orchestrator.

- Orchestrator reads updated `state.json`, spawns next agent:
  - `clean` → `general-purpose` runs BUGTEAM phase (bugteam via `Skill`
    when available, else inline by reading bugteam `SKILL.md`).
  - Exited on `dirty` (5e) with actionable inline threads → spawn same
    fix worker as "audit result with findings". Do **not** spawn
    `clean-coder` when monitor only saw `inline_lag` (5c retries) without
    reaching 5e — that path retries or escalates via `inline_lag_streak ≥
    3` hard blocker, not fix pass.

## What orchestrator does per tick

1. Per-tick `tick_count` bump for every non-terminal PR under `prs`.
2. Read `state.json`.
3. Each PR with new subagent results → spawn next agent per rules, all
   in one parallel message.
4. Re-read `state.json` if needed for scheduling.
5. Call `ScheduleWakeup` with appropriate delay.
6. Nothing else.

## Memory

Run directory `<TMPDIR>/pr-converge-<session_id>/` holds `state.json` and
optional `converged.log`. Keep from first create until every PR under `prs`
is `converged` or `blocked`, or **Stop conditions** ends loop. Safe to
delete folder after — `update_pull_request(draft=false)` on GitHub is
canonical record. Folder skill, not a plugin package; do **not** rely
on `${CLAUDE_PLUGIN_DATA}`. OS/disk cleanup of `<TMPDIR>` (reboot, policy)
can remove files mid-run — environmental risk.

**`converged.log` (multi-PR only — requires `state.json`):**

- **Path:** sibling of `state.json`.
- **Format:** one tab-separated row per converged PR: ISO8601 UTC,
  owner/repo#number, bugbot SHA, bugteam SHA.
- **Append site:** agent running `update_pull_request(pullNumber=NUMBER, owner=OWNER, repo=REPO, draft=false)`. Append **before**
  locked `state.json` publish so log row survives failed merge.
- **Never read inside loop.** User / follow-up tooling only.

Single-PR runs without `state.json`: do **not** append `converged.log`;
in-conversation summary plus GitHub ready state suffice.
