# End-of-run gotcha recommendations

Shared close-out for **every skill**. After the skill's main work finishes,
recommend pasteable gotchas from issues **this run** hit.

## When

- **Run:** at end of work, after the deliverable, when this run hit issues.
- **Clean run:** end with the deliverable only.

## What counts as an issue

Keep only items that **bit this run**:

- Wrong **path, file, or config**
- **Command / CLI** failed or needed different flags
- **Auth, permission, or environment** blocked a step
- **Data shape** mismatch (empty set, wrong schema, bad field)
- **Tool, UI, or selector** missed the target
- **Timing** needed a retry or longer wait
- **Dependency or install** gap or wrong version
- **Output format** wrong for the next step
- A **workaround** required to finish

## What to produce

A short **Gotcha recommendations** block for the user:

1. **One bullet per issue** — what failed + the **exact fix** that worked.
2. **Prefer a split** — keep the skill bullet to one short line; put longer
   context in a skill `reference/` doc and link it.
3. Write text the user can **paste** into the skill's `## Gotchas` (or into a
   new `reference/<slug>.md` with a one-line link from the skill).

### Shape

```markdown
## Gotcha recommendations

- **<short gotcha>.** Exact fix. More: [`reference/<slug>.md`](reference/<slug>.md)
```

When the fix fits one line, put the full fix in the bullet.

## Rules

- **Recommend only** — apply skill edits when the user asks.
- **Lived issues only** — keep only issues this run hit.
- **Short hub, deep ref** — skill gotcha names the trap; ref doc holds the walkthrough.
