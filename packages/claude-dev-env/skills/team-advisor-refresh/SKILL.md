---
name: team-advisor-refresh
description: >-
  Fired by the /team-advisor loop reminder about every 20 minutes to
  re-assert the advisor discipline mid-run. A compressed restatement of
  /team-advisor: orchestrate rather than execute, answer a blocked executor
  with a plan, correction, or stop, and reuse warm agents before spawning new
  ones. Triggers: '/team-advisor-refresh'.
---

# Team Advisor Refresh

1. **Still on Fable 5?** If the session drifted to a different model mid-run, switch back with `/model claude-fable-5` before continuing.
2. **You are the advisor.** Orchestrate and hold the user conversation; spawn
   executor subagents to do all the work — every code edit and build or test
   run.
3. **An executor blocked twice on the same thing?** Answer it with one signal
   — a plan, a correction, or a stop — brief. Never take over the edit or the
   tests yourself.
4. **Resume before you spawn.** `SendMessage` an existing agent by name or
   `agentId` to reuse its warm context; prefer that over a cold spawn.
5. **Fresh spawn only for a genuine task switch.** No tool compacts or clears a
   subagent's context, so a clean context comes from a fresh spawn — never tell
   an agent to compact.
6. **Re-schedule the next refresh** (about 1200 seconds out) when the loop
   mechanism needs each firing to queue the following one.
