# copilot-review

Spawns a background subagent that polls the GitHub Copilot reviewer on the current PR, fixes unaddressed findings, and re-requests review each tick until the PR is clean. Triggered by `/copilot-review`, `watch copilot`, `babysit copilot review`, or `keep re-requesting copilot`.

## Purpose

The main session gathers PR context (number, HEAD SHA, owner/repo, branch), spawns a self-terminating background subagent with a fully filled-in prompt, and returns control at once. The subagent loops on a 5-minute `ScheduleWakeup` cadence: fetch Copilot's latest review, TDD-fix any inline findings, push a commit, reply inline, re-request review. It stops on convergence, a persistent blocker, `TaskStop`, or after 20 ticks.

## Key file

| File | Purpose |
|---|---|
| `SKILL.md` | Four-step orchestration (opt-out check, gather PR context, spawn subagent, report to user), the verbatim subagent prompt template with all placeholders, fix protocol, stop conditions, and ground rules (one commit per tick, honor hooks, preserve draft state, use `copilot-pull-request-reviewer[bot]` with the `[bot]` suffix). |

## Environment opt-out

Set `CLAUDE_REVIEWS_DISABLED=copilot` to disable. The skill checks this before spawning anything.
