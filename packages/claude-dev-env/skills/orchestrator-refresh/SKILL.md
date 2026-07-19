---
name: orchestrator-refresh
description: >-
  Fired by the /orchestrator one-shot loop reminder to re-assert the advisor
  discipline mid-run: orchestrate, route hard decisions to the shared advisor
  (ENDORSE / CORRECTION / PLAN / STOP — SendMessage on Claude, Claude CLI chain
  on a third-party host), reuse warm agents. Terminates when status_gate says
  stop. Triggers: '/orchestrator-refresh'.
---

# Orchestrator Refresh

Detect the host profile first (see Host profiles in
[`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md)).
Re-assert the discipline for that host only — do not invent an Agent-tool
Claude `session-advisor` spawn on a third-party host.

## 0. status_gate first (deterministic)

Before anything else this firing, from the repo cwd (or with
`$ORCHESTRATOR_RUN_STATUS_FILE` set):

```
python "%USERPROFILE%\.claude\skills\orchestrator\scripts\status_gate.py" should-reschedule [--run-slug SLUG]
```

(On Unix: `~/.claude/skills/orchestrator/scripts/status_gate.py`. From a
package checkout: `skills/orchestrator/scripts/status_gate.py`. Pass the
same `--run-slug` used at activate, if any.)

| Exit | Action |
|---|---|
| **1** | Stop. Cancel any pending host schedule for this loop if the host allows it. Report that the run is inactive/done. **Do not** re-arm. Do not spawn. |
| **0** | Continue with steps 1–6 below. |

After ledger reconcile in step 1: if every task is completed/cancelled and no
executor is running, run:

```
python "%USERPROFILE%\.claude\skills\orchestrator\scripts\status_gate.py" set --status done [--run-slug SLUG]
```

then stop without re-arming (same as exit 1).

1. **Reconcile the task ledger first.** Call `TaskList` before anything else
   this firing (after the gate). The ledger is stale when any of these holds: a running or
   finished executor has no `in_progress` task naming it as owner; a finished
   executor's task is still open (or was closed without its result merged);
   the next phase you will dispatch has no pending task; a `blockedBy` link
   contradicts the actual run order. Fix every mismatch with TaskCreate /
   TaskUpdate in this same firing — never defer reconciliation to "when the
   agent reports".
2. **You are the orchestrator.** Orchestrate and hold the user conversation;
   spawn executor subagents to do all the work — every code edit and build or
   test run.
3. **Hard decisions go to the shared advisor.**
   - **Claude host:** executors consult the warm `session-advisor` via
     `SendMessage` and receive one of four signals — ENDORSE, CORRECTION, PLAN,
     or STOP. The orchestrating session routes its own hard decisions the same
     way and keeps its tool use to orchestration and light verification reads.
   - **Third-party host:** the advisor is a max-tier Claude CLI bind owned by this
     session (`claude_chain_runner.py`, Fable high then Opus max). Do **not**
     spawn `session-advisor` via Agent and do **not** tell executors to
     SendMessage a separate advisor agent. Executors report blockers to this
     session; consult the Claude CLI advisor and relay ENDORSE / CORRECTION /
     PLAN / STOP. When the CLI bind is unreachable, fail closed and report to
     the user — do not answer the four signals as this third-party session.
4. **Resume before you spawn.** `SendMessage` an existing *executor* agent by
   name or `agentId` to reuse its warm context; prefer that over a cold spawn.
   (On a third-party host this is executor reuse only — advisor re-bind stays on the CLI
   chain path in the shared protocol.)
5. **Fresh spawn only for a genuine task switch.** No tool compacts or clears a
   subagent's context, so a clean context comes from a fresh spawn — never tell
   an agent to compact.
6. **One-shot re-arm only if the gate still allows it.** Re-run
   `should-reschedule` (same `--run-slug` if any). Exit 0 → `ScheduleWakeup`
   once with about 1200–2700 seconds delay and prompt
   `/orchestrator-refresh` (plus `--run-slug SLUG` when used; never
   recurring / never cadence). Exit 1 → stop; do not schedule.
