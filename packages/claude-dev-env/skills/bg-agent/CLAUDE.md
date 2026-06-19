# bg-agent

Delegates a task to a background agent so the main session stays free. Triggered by `/bg-agent`, `bg-agent`, or `background agent for this`.

## Purpose

This skill picks a suitable agent type for the task, spawns it via the `Agent` tool with `run_in_background: true`, and returns control at once. The spawned agent notifies on completion. Other skills (such as `gotcha`) invoke this skill to offload their own PR-creation steps.

## Key file

| File | Purpose |
|---|---|
| `SKILL.md` | Full instructions: how to parse the task argument, how to pick an agent type, how to write a self-contained spawn prompt, and how to report spawn to the user. |

## How this skill is invoked

The user types `/bg-agent <task description>` or a calling skill invokes it by name. The skill always spawns with `run_in_background: true` — it never runs the task inline in the main session.
