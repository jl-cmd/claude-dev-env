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

Two turns in order (same pattern as lean AskUserQuestion + ELI11 chat):

1. **Print findings in chat first** — ELI11, clean, concise (see below).
2. **Then** `AskUserQuestion` — lean question + short option labels only.
3. **On confirm only** — file selected gotchas via **`issue-tracker`**.

### 1. Chat findings (always first)

Print a **Gotcha recommendations** block in the assistant message **before**
any `AskUserQuestion` call. Follow `eli11-replies` + `plain-language`:

- **Bold lead** on each bullet
- **One idea per line**
- **What failed + exact fix** that worked
- **Prefer a split** — short bullet; longer walkthrough in
  `reference/<slug>.md` with a link
- **Paste-ready** for the skill `## Gotchas`

```markdown
## Gotcha recommendations

- **<short gotcha>.** Exact fix. More: [`reference/<slug>.md`](reference/<slug>.md)
```

When the fix fits one line, put the full fix in the bullet.

**Detail lives in chat** (and refs). Keep it out of the question widget.

### 2. Issue offer (`AskUserQuestion`)

**After** the chat block is visible, call `AskUserQuestion` once.

The form must stand alone: a skimmer who only opens the widget still sees
**what broke** and **why filing helps**.

- **Header:** `File issues` (≤12 chars)
- **Question:** short, action-first — e.g. `File a GitHub issue for any of these gotchas?`
- **multiSelect:** `true` when more than one gotcha
- **Each option (required substance):**
  - **label:** `File: <short name>` (what it is)
  - **description:** one tight sentence = **what bit you** + **exact fix** (why it matters)
- Mirror session-log decision extraction: the choice text carries the finding,
  not only a topic word

**Example option:**

| Field | Example |
|---|---|
| label | `File: Catalog path` |
| description | `CLI missed the catalog off-repo. Fix: run from repo root with data/midjourney_sref_catalog.json.` |

**Only on confirm:** file selected gotchas through **`issue-tracker`** (dedup +
epic). One issue per selection. Body: gotcha summary, exact fix, cold-reader
evidence.

When the run was clean, skip the chat block and the offer.

## Rules

- **Chat first, then ask** — never open AskUserQuestion without the ELI11
  findings already printed in that turn.
- **Lean question block** — short question + short labels; detail stays in chat
  (standing pattern: lean AskUserQuestion / PR #720 family).
- **Recommend only** — apply skill edits when the user asks.
- **File only on confirm** — selected gotchas only, via `issue-tracker`.
- **Lived issues only** — keep only issues this run hit.
- **Short hub, deep ref** — skill gotcha names the trap; ref holds the walkthrough.
