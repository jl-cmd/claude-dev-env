---
name: orchestrator-refresh
description: >-
  Fired by the /orchestrator loop reminder about every 20 minutes to
  re-assert the advisor discipline mid-run. A compressed restatement of
  /orchestrator: orchestrate rather than execute, answer a blocked executor
  with a plan, correction, or stop, and reuse warm agents before spawning new
  ones. Triggers: '/orchestrator-refresh'.
---

# Orchestrator Refresh

1. **You are the advisor.** Orchestrate and hold the user conversation; spawn
   executor subagents to do all the work — every code edit and build or test
   run.
2. **An executor blocked twice on the same thing?** Answer it with one signal
   — a plan, a correction, or a stop — brief. Never take over the edit or the
   tests yourself.
3. **Resume before you spawn.** `SendMessage` an existing agent by name or
   `agentId` to reuse its warm context; prefer that over a cold spawn.
4. **Fresh spawn only for a genuine task switch.** No tool compacts or clears a
   subagent's context, so a clean context comes from a fresh spawn — never tell
   an agent to compact.
5. **Re-schedule the next refresh** (about 1200 seconds out) when the loop
   mechanism needs each firing to queue the following one.
