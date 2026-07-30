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

Chat open uses **exactly two prose lines**:

1. What we were doing.
2. Why these notes matter.

### 1. Chat findings (always first)

Print **before** any `AskUserQuestion`.

#### One sentence per line (HARD)

Apply to **every prose line** in the close-out (setup, gotcha name, wrong, fix, form question, option description).

| Rule | Required |
|---|---|
| **One sentence** | Exactly one of `.` `?` `!` at the end of the line |
| **No second clause join** | No em-dash, en-dash, semicolon, or colon used to glue two clauses |
| **No "and/but/so" pile-ons** | One idea only; put the next idea on the next line |
| **Blank lines OK** | Separators are not sentences |
| **ASCII fences OK** | Diagram lines are diagrams, not prose sentences |

**Self-check before send:** for each prose line, if you can split it into two true sentences, **split it**.

#### Each gotcha mini-block

1. One line: plain name.
2. One line: what went wrong.
3. One line: the fix (one action).
4. ASCII diagram (required for path, flag, or before/after).

```text
## Session close-out

We built phone-theme image prompts from a project style catalog.
Keep these traps so the next run stays smooth.

## Gotcha recommendations

### Wrong folder for the catalog file

The style-code picker looked outside the project.
It failed.
Fix: open the terminal at the project root.
Use the file data/midjourney_sref_catalog.json.

  +----------------+        +----------------------------------+
  | wrong folder   | -----> | picker fails                     |
  +----------------+        +----------------------------------+
  | project root   | -----> | data/midjourney_sref_catalog.json|
  +----------------+        +----------------------------------+
```

### 2. Issue offer (`AskUserQuestion`)

**Only after** the chat block.

| Field | Limit |
|---|---|
| **Question** | One sentence. Brief. |
| **Header** | `File issues` |
| **multiSelect** | `true` when more than one gotcha |
| **label** | Plain cold-reader name |
| **description** | One sentence only (what went wrong, or the fix — pick one; chat has the rest) |

**Everything longer stays in chat.**
The form is the decision only.

**On confirm:** file selected gotchas through **`issue-tracker`**.
One issue per selection.
Body written for a cold reader.

Clean run: skip chat block and offer.

## Rules

- **Cold-reader first.**
- **Chat first, then ask.**
- **One sentence per prose line (HARD).**
- **ASCII for every path, flag, or before/after gotcha.**
- **AskUserQuestion stays one brief sentence.**
- **Detail and ASCII live in chat.**
- **Recommend only.**
- **File only on confirm** via `issue-tracker`.
- **Lived issues only.**
