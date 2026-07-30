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

1. **Show findings in chat** (cold-reader, user-friendly).
2. **Then** `AskUserQuestion` (one brief sentence + short options).
3. **On confirm only** — file via **`issue-tracker`**.

### Cold-reader frame (required)

Assume the user **was away** and has **zero context**.
Open chat with **one or two lines** that answer:

- **What we were doing** (the job in plain words).
- **Why these notes matter** (so the next run does not re-hit the same traps).

Use everyday words.
Name tools and paths only when the reader needs them to act.

### 1. Chat findings (always first)

Print **before** any `AskUserQuestion`.
**One sentence per line. Max.**
ELI11: bold lead, short lines, scannable.

Each gotcha:

- **Plain name** a stranger understands (not an in-joke code word).
- **What went wrong** in full English.
- **Exact fix** they can do next time.

Prefer a **user-friendly layout**:

- Bold names + short lines
- Optional **ASCII** when it clarifies (flow, before/after)
- Links to `reference/<slug>.md` when the walkthrough is longer

```text
## Session close-out

We built Midjourney theme prompts that attach style codes from a catalog file.
These traps cost time this run — keep them for the next one.

## Gotcha recommendations

- **Wrong folder for the catalog file.**
  The style-code picker looked for the catalog outside the project and failed.
  Fix: open a terminal at the project root and use data/midjourney_sref_catalog.json.

  wrong folder  -->  picker fails
  project root  -->  data/midjourney_sref_catalog.json  OK
```

Paste-ready for skill `## Gotchas` when the user wants it in the skill.

### 2. Issue offer (`AskUserQuestion`)

**Only after** the chat block.

**Hard limits on the widget:**

- **Question:** **one sentence**, brief
  (e.g. `File a GitHub issue for any of these so we keep the fix?`)
- **Header:** `File issues`
- **multiSelect:** `true` when more than one gotcha
- **label:** plain name a cold reader gets (`File: Wrong catalog folder`)
- **description:** **one short sentence** = what went wrong + fix
  (still readable with no chat history)

**Everything longer stays in chat** (setup lines, ASCII, refs).
The form is the decision only.

**On confirm:** file selected gotchas through **`issue-tracker`**.
One issue per selection.
Body written for a **cold reader**: what the job was, what broke, exact fix, evidence.

Clean run: skip chat block and offer.

## Rules

- **Cold-reader first** — frame the job before naming traps.
- **Chat first, then ask.**
- **One sentence per chat line.**
- **AskUserQuestion = one brief sentence** + plain short labels.
- **Detail and ASCII live in chat**, not in the form tree.
- **Recommend only** — skill edits when the user asks.
- **File only on confirm** via `issue-tracker`.
- **Lived issues only.**
