# End-of-run gotcha recommendations

**Shared close-out** for every skill. After the deliverable, recommend pasteable
gotchas from issues **this run** hit.

## When

- **With issues:** end of work, after the deliverable.
- **Clean run:** end with the deliverable only.

## What counts

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

**Gotcha recommendations** for the user:

1. **One bullet per issue** — what failed + the **exact fix** that worked.
2. **Prefer a split** — short skill bullet; longer walkthrough in
   `reference/<slug>.md` with a link.
3. **Paste-ready** text for the skill `## Gotchas` (or a new ref + one-line link).
4. **Issue offer** — after the recommendations print, ask via `AskUserQuestion`
   whether to **file a GitHub issue** for each gotcha (session-log style).

### Shape

```markdown
## Gotcha recommendations

- **<short gotcha>.** Exact fix. More: [`reference/<slug>.md`](reference/<slug>.md)
```

When the fix fits one line, put the full fix in the bullet.

### Issue offer (`AskUserQuestion`)

After the recommendations block, for each recommended gotcha ask the user
via `AskUserQuestion` (same pattern as session-log decision extraction):

> "Gotcha: [summary + exact fix]. File a GitHub issue for it?"

**Shape of the question:**

- **Header:** `File issues` (12 chars or fewer)
- **multiSelect:** `true` when more than one gotcha is on the table
- **Options:** one option per gotcha — label `File: <short gotcha>`
- **Recommended option first** when a default makes sense

**Only on confirm:** file the selected gotchas through the **`issue-tracker`**
skill (or agent) so dedup and epic linking apply. One issue per selected
gotcha. Body carries the gotcha summary, the exact fix that worked, and
enough evidence for a cold reader.

When the run was clean, skip recommendations and this offer.

## Rules

- **Recommend only** — apply skill edits when the user asks.
- **File only on confirm** — selected gotchas only, via `issue-tracker`.
- **Lived issues only** — keep only issues this run hit.
- **Short hub, deep ref** — skill gotcha names the trap; ref holds the walkthrough.
