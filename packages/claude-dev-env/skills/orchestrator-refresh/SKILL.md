---
name: orchestrator-refresh
description: >-
  Fired by the /orchestrator loop reminder about every 20 minutes to
  re-assert the advisor discipline mid-run: orchestrate, route hard decisions
  to the shared advisor (ENDORSE / CORRECTION / PLAN / STOP — SendMessage on
  Claude, Claude CLI chain on a third-party host), reuse warm agents. Triggers:
  '/orchestrator-refresh'.
---

# Orchestrator Refresh

Detect the host profile first (see Host profiles in
[`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md)).
Re-assert the discipline for that host only — do not invent an Agent-tool
Claude `session-advisor` spawn on a third-party host.

1. **Reconcile the task ledger first.** Call `TaskList` before anything else
   this firing. The ledger is stale when any of these holds: a running or
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
5. **Re-schedule the next refresh** (about 1200 seconds out) when the loop
   mechanism needs each firing to queue the following one.
