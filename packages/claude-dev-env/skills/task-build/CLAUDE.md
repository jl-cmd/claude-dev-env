# task-build

Gathers every open task in the current session and registers each one on the task list with `TaskCreate`.

**Trigger:** `/task-build`, "build my task list", "capture these tasks", "add open tasks to the task list", "track these".

## Purpose

Collects outstanding work from the conversation, `$ARGUMENTS`, and any plan documents or `TodoWrite` items raised this session, then creates one task per open item — skipping anything already tracked or already complete.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | The complete skill — four steps (read current list, find open tasks, create one task per item, report). No companion files. |

## How the skill runs

1. Calls `TaskList` to read what is already tracked — prevents duplicates.
2. Scans `$ARGUMENTS`, the conversation, and any plan or checklist items for open, actionable work.
3. Calls `TaskCreate` for each untracked item with a short imperative `subject`, a `description` of what done looks like, and an optional `activeForm` for the spinner.
4. Reports how many tasks were added and how many were already tracked.

## Conventions

- This skill only records tasks — it does not start, assign, or complete them.
- Use `TaskUpdate` to set status or owner after the list is built.
- `disable-model-invocation: true` is not set; the skill uses model judgment to classify open vs. complete items.
