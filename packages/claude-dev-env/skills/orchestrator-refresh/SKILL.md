---
name: orchestrator-refresh
description: >-
  Re-assert orchestrator discipline on a one-shot delayed wake: ledger
  reconcile, advisor routing, warm executor reuse, single-pending re-arm
  via status_gate. Terminates when the gate says stop. Triggers:
  '/orchestrator-refresh', orchestrator-refresh, refresh the orchestrator
  loop, re-arm orchestrator.
---

# Orchestrator Refresh

Detect the host profile first (see Host profiles in
[`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md)).
Re-assert the discipline for that host only — do not invent an Agent-tool
Claude `session-advisor` spawn on a third-party host.

## 0. status_gate first (deterministic)

Script home (prefer install path, else package checkout):

- `%USERPROFILE%/.claude/skills/orchestrator/scripts/status_gate.py`
- `~/.claude/skills/orchestrator/scripts/status_gate.py`
- `skills/orchestrator/scripts/status_gate.py`

Pass the same `--run-slug` used at activate, if any.

### 0a. begin-firing (consume prior re-arm)

```
python <status_gate.py> begin-firing [--run-slug SLUG]
```

| Exit | Action |
|---|---|
| **1** | End the refresh. Cancel matching host schedules for `/orchestrator-refresh` if the host allows. Report inactive/done. **Do not** re-arm. Do not spawn. Any work already in flight keeps running. |
| **0** | Latch cleared. Continue with steps 1–6. |

### 0b. Done after ledger (step 1)

After ledger reconcile: if every task is completed/cancelled and no
executor is running:

```
python <status_gate.py> set --status done [--run-slug SLUG]
```

Cancel matching host schedules; stop without re-arming.

## The refresh never interrupts the run

A refresh firing reinforces discipline alongside work already in flight.
It never pauses, cancels, or waits on a running executor. Reconcile the
ledger, re-assert the routing, re-arm once, and hand control straight back
to the work in progress.

Inside the re-arm protocol (step 6), every "stop" ends the *re-arm* and
nothing else. A `should-reschedule` exit 1 means no schedule is created this
firing, and a `claim-rearm` exit 1 means the schedule just created is
cancelled; either way the session keeps orchestrating in the same turn.

Two stops end the whole firing, and both leave running executors alone:
`begin-firing` exit 1 (step 0a) and the done branch (step 0b). Each means the
run is finished, not active, or has no readable status file, so the refresh
reports and adds nothing further. A fail-closed advisor bind (step 3) stops
advisor consultation alone; the firing still reconciles the ledger, re-arms
once, and reports the unreachable advisor.

## Discipline steps

1. **Reconcile the task ledger first.** Call `TaskList` after the gate.
   The ledger is stale when any of these holds: a running or finished
   executor has no `in_progress` task naming it as owner; a finished
   executor's task is still open (or was closed without its result
   merged); the next phase you will dispatch has no pending task; a
   `blockedBy` link contradicts the actual run order. Fix every mismatch
   with TaskCreate / TaskUpdate in this same firing — never defer.
2. **You are the orchestrator.** Orchestrate and hold the user
   conversation; spawn executor subagents for every code edit and build
   or test run.
   - **Worker model.** Every coding spawn sets `model: sonnet` on a
     Claude host, or the resolver-printed sonnet-equivalent id on a
     third-party host, and fails closed — see Workflow Agent Routing in
     [`skills/orchestrator/SKILL.md`](../orchestrator/SKILL.md#workflow-agent-routing).
   - **Focused tickets.** One mechanical done-check per ticket; resume a
     warm agent with a thin next-slice ticket rather than a fresh cold
     spawn, and keep thick context in the assignment file.
3. **Hard decisions go to the shared advisor.**
   - **Claude host:** executors consult the warm `session-advisor` via
     `SendMessage` (ENDORSE / CORRECTION / PLAN / STOP). This session
     routes the same way; keep tool use to orchestration and light
     verification reads.
   - **Third-party host:** advisor is a max-tier Claude CLI bind owned
     by this session (`claude_chain_runner.py`, Fable high then Opus
     max). Do **not** spawn `session-advisor` via Agent. Executors
     report blockers here; consult the CLI advisor and relay signals.
     If the CLI bind is unreachable, fail closed — do not answer the
     four signals as this third-party session.
4. **Resume before you spawn.** `SendMessage` an existing *executor* by
   name or `agentId` before a cold spawn. (Third-party: executor reuse
   only — advisor stays on the CLI chain.)
5. **Fresh spawn only for a genuine task switch.** Never tell an agent
   to compact for a clean context.
6. **Single-pending re-arm only.** Same protocol as the orchestrator
   skill (host-agnostic; **create then claim**):

   1. Cancel matching schedules only when the host can list/cancel by
      prompt (`/orchestrator-refresh` + `--run-slug` if used). On Claude,
      skip selective cancel — the latch is the sole stacking enforcement.
   2. `python <status_gate.py> should-reschedule [--run-slug SLUG]`
      - Exit **1** → stop; do not schedule.
      - Exit **0** → continue.
   3. Create **exactly one** non-recurring delayed wake (~1200–2700s)
      with prompt `/orchestrator-refresh` (plus `--run-slug` when used).
      Host one-shot tool only (on Claude: `ScheduleWakeup`). Never
      recurring / never cadence / never a second create this firing.
   4. `python <status_gate.py> claim-rearm [--run-slug SLUG]` right
      after a successful create. Exit 1 → cancel that schedule and stop.
   5. If create fails: do not claim; stop or retry once from cancel.

## Gotchas

- **Stacking loops.** A second schedule create while one is already
  queued multiplies firings. Cancel → `should-reschedule` → one create
  → `claim-rearm`. Never claim before create on Claude (PreToolUse
  denies `ScheduleWakeup` when pending).
- **Skipping `begin-firing`.** Prior `rearm_pending` stays set; re-arm
  stays denied. Always run step 0a first.
- **Create without claim.** Skip claim after create and a second create
  can stack. Claim immediately after success.

## File Index

| File | Purpose |
|---|---|
| `SKILL.md` | Refresh firing steps; points at orchestrator `status_gate.py`. |

## Folder Map

- `SKILL.md` — this skill (thin); gate implementation lives under
  `skills/orchestrator/scripts/`.
- Advisor policy:
  [`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md).
