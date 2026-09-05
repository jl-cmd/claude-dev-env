---
name: hitl
description: >-
  Maintain human-in-the-loop scope reporting; bound worker orchestration. Triggers: /hitl, HITL, human in the loop, out-of-scope work, scope update, worker status, Sol worker, Claude worker, Grok worker.
disable-model-invocation: true
user-invocable: true
argument-hint: "[optional task context]"
---

# HITL

Initialize these human-in-the-loop rules for the active agent when `/hitl` is invoked.

## Principle

Keep the human informed when work outside the stated scope appears. Name the item, say why it is outside scope, and state the path taken.

## Gotchas

- Do not silently expand scope.
- A worker's availability does not change the user's scope.
- Sol, Claude, and Grok workers follow these same rules.
- Preserve the requested work when an out-of-scope item appears.

## When this applies

Apply this skill only after explicit `/hitl` invocation. Treat any argument as context. Do not use it to add work to the user's request.

## Process

1. Read the active user scope before each material action.
2. Keep work inside that scope.
3. If an out-of-scope item appears, pause the affected path, report the item and the path taken, and ask for direction when needed.
4. Use a low-effort Sol, Claude, or Grok worker only when the work stays in scope or the human has received the needed status. Give the worker this same scope rule.
5. Report the worker choice and outcome, then continue the stated task.

## File index

| Path | Purpose |
|---|---|
| `SKILL.md` | Explicit `/hitl` operating prompt. |

## Folder map

`hitl/` contains only `SKILL.md`.
