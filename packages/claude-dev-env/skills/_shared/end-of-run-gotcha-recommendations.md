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

1. **Show findings in chat** (cold-reader, ASCII-heavy).
2. **Then** `AskUserQuestion` (one brief sentence + short options).
3. **On confirm only** — file via **`issue-tracker`**.

### Cold-reader frame (required)

Assume the user **was away** and has **zero context**.

Chat open (exactly **two** lines, **one sentence each**):

1. **What we were doing** in plain words.
2. **Why these notes matter** for the next run.

### 1. Chat findings (always first)

Print **before** any `AskUserQuestion`.

**Line rules (hard):**

- **One sentence per line. Max. No exceptions.**
- **Bold lead** on each line that names a fact.
- **No multi-clause bullets** that smuggle a second sentence.

**Each gotcha is a mini-block:**

1. One line: **plain name** a stranger understands.
2. One line: **what went wrong.**
3. One line: **exact fix.**
4. **ASCII diagram** (required when a path, flag, or before/after is involved).

Prefer boxes, arrows, and before/after maps over extra prose.

```text
## Session close-out

We built phone-theme image prompts that pull style codes from a project catalog.
These traps burned time this run — keep them for the next one.

## Gotcha recommendations

### Wrong folder for the catalog file

The style-code picker looked outside the project and failed.
Fix: run from the project root and use data/midjourney_sref_catalog.json.

  +------------------+      +----------------------------------+
  | wrong folder     | ---> | picker fails                     |
  +------------------+      +----------------------------------+
  | project root     | ---> | data/midjourney_sref_catalog.json|
  +------------------+      +----------------------------------+
```

Paste-ready for skill `## Gotchas` when the user wants it in the skill.

### 2. Issue offer (`AskUserQuestion`)

**Only after** the chat block.

**Hard limits on the widget:**

- **Question:** **one sentence**, brief
- **Header:** `File issues`
- **multiSelect:** `true` when more than one gotcha
- **label:** plain cold-reader name
- **description:** **one short sentence** = what went wrong + fix

**Everything longer stays in chat** (setup, ASCII, refs).
The form is the decision only.

**On confirm:** file selected gotchas through **`issue-tracker`**.
One issue per selection.
Body written for a **cold reader**.

Clean run: skip chat block and offer.

## Rules

- **Cold-reader first.**
- **Chat first, then ask.**
- **One sentence per chat line.**
- **ASCII for every path/flag/before-after gotcha.**
- **AskUserQuestion = one brief sentence** + plain short labels.
- **Detail and ASCII live in chat.**
- **Recommend only** — skill edits when the user asks.
- **File only on confirm** via `issue-tracker`.
- **Lived issues only.**
