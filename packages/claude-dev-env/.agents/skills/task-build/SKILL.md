---
name: task-build
description: "Gather open session tasks and register them with the best available task or plan tool. Triggers: '/task-build', 'build my task list', 'capture these tasks', 'add open tasks to the task list', 'track these', task list, update plan."
argument-hint: "[optional: a list of tasks to capture, or omit to scan the session]"
---

# Task Build

Collect every open task and put it on the session task list or plan using the best available host tool. Read [tool-routing.md](reference/tool-routing.md) only when choosing or adapting the host-tool path.

## Instructions

1. **Read the current list first.** Use the read operation paired with the selected host tool when one exists. If `update_plan` is the selected tool, inspect the current visible plan when available because `update_plan` replaces the full plan.

2. **Find every open task.** Gather all outstanding work from these sources:
   - `$ARGUMENTS`, when the user passed a list.
   - The current conversation: anything the user asked for that is not yet done.
   - Plan documents, checklists, or `TodoWrite` items raised in this session.

   An open task is any concrete, actionable item that is not finished. Skip anything already complete and anything already on the list.

3. **Register one item per task.** Prefer `update_plan` when it is available. Otherwise use the first supported task-list method described in [tool-routing.md](reference/tool-routing.md), preserving the complete existing list when the selected tool replaces it.

4. **Report the result.** State how many tasks you added and how many were already tracked, then list the new subjects.

## Scope

This skill only records tasks. It does not start, assign, or complete them. Report the selected tool, how many items were added, and how many were already tracked. Use the matching host operation to change status later.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Task discovery and registration hub |
| `reference/tool-routing.md` | On-demand host-tool selection and field mapping |

## Folder map

- `reference/` — host-tool routing details loaded only when needed
