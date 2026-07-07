---
name: advisor-refresh
description: >-
  Fired by the /advisor loop reminder about every 20 minutes to re-assert the
  advisor discipline mid-run. A compressed restatement of /advisor: keep
  driving as the executor, consult the tool-less advisor at a hard blocker,
  and reuse warm agents before spawning new ones. Triggers: '/advisor-refresh'.
---

# Advisor Refresh

A person never invokes this by hand; the `/advisor` loop fires it. Run this
checklist, then return to the task.

1. **You are the executor-orchestrator.** Keep driving the task end to end.
2. **Blocked twice on the same thing?** Consult the `code-advisor` agent with
   the task, what you tried, and the exact blocker. It replies with one signal
   — a plan, a correction, or a stop — holds no tools, and writes nothing the
   user reads. Resume the moment the reply lands.
3. **Resume before you spawn.** `SendMessage` an existing agent by name or
   `agentId` to reuse its warm context; prefer that over a cold spawn.
4. **Fresh spawn only for a genuine task switch.** No tool compacts or clears a
   subagent's context, so a clean context comes from a fresh spawn — never tell
   an agent to compact.
5. **Re-schedule the next refresh** (about 1200 seconds out) when the loop
   mechanism needs each firing to queue the following one.
