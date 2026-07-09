---
name: orchestrator-refresh
description: >-
  Fired by the /orchestrator loop reminder about every 20 minutes to
  re-assert the advisor discipline mid-run: orchestrate, route hard decisions
  to the shared advisor (ENDORSE / CORRECTION / PLAN / STOP — SendMessage on
  Claude, self-as-advisor on Grok), reuse warm agents. Triggers:
  '/orchestrator-refresh'.
---

# Orchestrator Refresh

Detect the host profile first (see Host profiles in
[`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md)).
Re-assert the discipline for that host only — do not invent a Claude
`session-advisor` spawn on a Grok host.

1. **You are the advisor-orchestrator.** Orchestrate and hold the user
   conversation; spawn executor subagents to do all the work — every code edit
   and build or test run.
2. **Hard decisions go to the shared advisor.**
   - **Claude host:** executors consult the warm `session-advisor` via
     `SendMessage` and receive one of four signals — ENDORSE, CORRECTION, PLAN,
     or STOP. The orchestrating session routes its own hard decisions the same
     way and keeps its tool use to orchestration and light verification reads.
   - **Grok host:** this session *is* the advisor (self-as-advisor). Do **not**
     spawn `session-advisor` and do **not** tell executors to SendMessage a
     separate advisor agent. Executors report blockers to this session; answer
     with ENDORSE / CORRECTION / PLAN / STOP inline.
3. **Resume before you spawn.** `SendMessage` an existing *executor* agent by
   name or `agentId` to reuse its warm context; prefer that over a cold spawn.
   (On Grok this is executor reuse only — not an advisor spawn.)
4. **Fresh spawn only for a genuine task switch.** No tool compacts or clears a
   subagent's context, so a clean context comes from a fresh spawn — never tell
   an agent to compact.
5. **Re-schedule the next refresh** (about 1200 seconds out) when the loop
   mechanism needs each firing to queue the following one.
