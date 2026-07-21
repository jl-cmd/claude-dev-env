# Task Tool Routing

Use the first available path in this order:

1. **`update_plan`** — preferred when exposed. Call it once with the complete plan. Map each task to `{step, status}`. Use `pending`, `in_progress`, or `completed`.
2. **`TaskList` + `TaskCreate`** — use the existing task-list workflow when `update_plan` is unavailable. Create one task per new item with `subject`, `description`, and optional `activeForm`.
3. **`TodoWrite`** — use when neither `update_plan` nor `TaskCreate` is exposed. Preserve the host's required schema and register the complete current task set.

Do not invent a tool name. Tool availability means the callable tool is exposed in the current session, not merely mentioned in documentation or in another host's skill.

## Status and replacement rules

- When a tool replaces the complete list, include existing unfinished items in the replacement payload.
- When a tool supports incremental creation, skip duplicates and completed items.
- If no task or plan tool is exposed, report that fact and keep the work unregistered; do not use a markdown checklist as a substitute.

## Reporting

State the selected tool, the number of new items, the number already tracked, and the new task subjects. If the fallback path was used, name the unavailable preferred tools briefly.
