---
name: task-build
description: "Gather every open task in the current session and register each one on the task list with TaskCreate. Use at the start of work, after a planning discussion, or whenever the user lists several things to do. Triggers: '/task-build', 'build my task list', 'capture these tasks', 'add open tasks to the task list', 'track these'."
argument-hint: "[optional: a list of tasks to capture, or omit to scan the session]"
---

# Task Build

Collect every open task and put it on the session task list. Each open task becomes one `TaskCreate` entry, so all the work is tracked and visible.

## Instructions

1. **Read the current list first.** Call `TaskList` to see what is already tracked. This keeps you from adding the same task twice.

2. **Find every open task.** Gather all outstanding work from these sources:
   - `$ARGUMENTS`, when the user passed a list.
   - The current conversation: anything the user asked for that is not yet done.
   - Plan documents, checklists, or `TodoWrite` items raised in this session.

   An open task is any concrete, actionable item that is not finished. Skip anything already complete and anything already on the list.

3. **Create one task per item.** For each open task that is not already tracked, call `TaskCreate` with:
   - `subject` — a short imperative title (e.g. "Fix login redirect").
   - `description` — what the task involves and how to tell it is done.
   - `activeForm` — the present-continuous form for the spinner (e.g. "Fixing login redirect"), when it adds clarity.

4. **Report the result.** State how many tasks you added and how many were already tracked, then list the new subjects.

## Scope

This skill only records tasks. It does not start, assign, or complete them. Use `TaskUpdate` to set an owner or change status once the list is built.
