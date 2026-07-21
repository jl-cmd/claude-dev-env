# task-build

Gathers every open task in the current session and registers each one with the best available task or plan tool.

**Trigger:** `/task-build`, "build my task list", "capture these tasks", "add open tasks to the task list", "track these".

## Purpose

Collects outstanding work from the conversation, `$ARGUMENTS`, and any plan documents or task items raised this session, then registers one item per open task — skipping anything already tracked or already complete.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Complete task discovery and registration workflow |
| `reference/tool-routing.md` | Progressive-disclosure routing and fallback rules |

## How the skill runs

1. Reads the current list or visible plan with the selected host tool — prevents duplicates.
2. Scans `$ARGUMENTS`, the conversation, and any plan or checklist items for open, actionable work.
3. Prefers `update_plan`; otherwise uses `TaskList`/`TaskCreate`, then `TodoWrite` as the fallback. See `reference/tool-routing.md` for field mapping.
4. Reports the selected tool, how many tasks were added, and how many were already tracked.

## Conventions

- This skill only records tasks — it does not start, assign, or complete them.
- Use the matching host operation to set status after the list is built.
- `disable-model-invocation: true` is not set; the skill uses model judgment to classify open vs. complete items.
