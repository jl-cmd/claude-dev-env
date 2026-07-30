# End-of-run gotcha recommendations

**Shared close-out** for every skill.
After the deliverable, recommend pasteable gotchas from issues **this run** hit.

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

**Order (hard):**

1. **Show findings in chat** (user-friendly, detail lives here).
2. **Then** `AskUserQuestion` (one brief sentence + short options).
3. **On confirm only** — file via **`issue-tracker`**.

### 1. Chat findings (always first)

Print **before** any `AskUserQuestion`.
**One sentence per line. Max.**
ELI11: bold lead, short lines, scannable.

Each gotcha line:

- **What bit you.**
- **Exact fix.**

Prefer a **user-friendly layout** in chat:

- Bullets with bold names
- Optional **ASCII infographic** when it clarifies (flow, before/after, map)
- Links to `reference/<slug>.md` when the walkthrough is longer

```text
## Gotcha recommendations

- **Catalog path.** CLI missed the catalog off-repo.
  Fix: run from repo root with data/midjourney_sref_catalog.json.

  cwd off-repo  -->  catalog miss
  cwd = repo    -->  data/midjourney_sref_catalog.json  OK
```

Paste-ready for skill `## Gotchas` when the user wants it in the skill.

### 2. Issue offer (`AskUserQuestion`)

**Only after** the chat block.

**Hard limits on the widget:**

- **Question:** **one sentence**, brief (e.g. `File a GitHub issue for any of these?`)
- **Header:** `File issues`
- **multiSelect:** `true` when more than one gotcha
- **label:** short name only (`File: Multi-code flag`)
- **description:** **one short sentence** = what bit you + fix (or omit if the chat block already said it)

**Everything longer stays in chat** (prose, ASCII, refs).
The form is the decision only.

**On confirm:** file selected gotchas through **`issue-tracker`**.
One issue per selection.
Body: summary, exact fix, cold-reader evidence.

Clean run: skip chat block and offer.

## Rules

- **Chat first, then ask.**
- **One sentence per chat line.**
- **AskUserQuestion = one brief sentence** + short labels.
- **Detail and ASCII live in chat**, not in the form tree.
- **Recommend only** — skill edits when the user asks.
- **File only on confirm** via `issue-tracker`.
- **Lived issues only.**
