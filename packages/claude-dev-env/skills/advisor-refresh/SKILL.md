---
name: advisor-refresh
description: >-
  Fired by the /advisor loop reminder about every 20 minutes to re-assert the
  advisor discipline mid-run. A compressed restatement of /advisor: keep
  driving as the executor, consult the tool-less advisor at a hard blocker,
  and reuse warm agents before spawning new ones. Triggers: '/advisor-refresh'.
---

# Advisor Refresh

1. **You are the executor-orchestrator.** Keep driving the task end to end.
2. **Resume before you spawn.** `SendMessage` an existing agent by name or
   `agentId` to reuse its warm context; prefer that over a cold spawn.
3. **Fresh spawn only for a genuine task switch.** No tool compacts or clears a
   subagent's context, so a clean context comes from a fresh spawn — never tell
   an agent to compact.
4. **Re-schedule the next refresh** (about 1200 seconds out) when the loop
   mechanism needs each firing to queue the following one.
5. **Spawn sub agents to do all the work, per the main advisor skill.
