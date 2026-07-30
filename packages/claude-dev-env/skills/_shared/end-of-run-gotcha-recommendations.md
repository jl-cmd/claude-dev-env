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

1. Show findings in chat.
2. Then `AskUserQuestion`.
3. On confirm only, file via `issue-tracker`.

### Cold-reader frame

Assume zero context.

**Exactly two setup lines** (one sentence each):

1. What we were doing.
2. Why these notes matter.

### 1. Chat findings (always first)

#### Sentence law (HARD)

| Rule | Required |
|---|---|
| **One sentence per prose line** | Exactly one terminal `.` `?` or `!` |
| **No clause glue** | No em-dash, semicolon, or colon joining two clauses |
| **One idea** | If you can split it, split it — or delete the extra idea |
| **Short** | Prefer under ~12 words |

#### Per gotcha (HARD shape)

| Part | Form |
|---|---|
| **Title** | Heading fragment only (not a sentence) |
| **Broke** | **One** sentence |
| **Fix** | **One** sentence |
| **ASCII** | Required for path, flag, or before/after |

**Cap: two prose sentences per gotcha.**
No third line of prose.

```text
## Session close-out

We built phone-theme prompts from a project style catalog.
Keep these traps for the next run.

## Gotcha recommendations

### Wrong catalog folder

The style picker failed outside the project.
Run from the project root with data/midjourney_sref_catalog.json.

  wrong folder  -->  fail
  project root  -->  data/midjourney_sref_catalog.json
```

### 2. Issue offer (`AskUserQuestion`)

Only after the chat block.

| Field | Limit |
|---|---|
| **Question** | One short sentence |
| **Header** | `File issues` |
| **label** | Plain name |
| **description** | One short sentence |

Detail and ASCII stay in chat.

**On confirm:** file via `issue-tracker`.
Cold-reader issue body.
Clean run: skip.

## Rules

- Cold-reader first.
- Chat first, then ask.
- Two prose sentences per gotcha max (broke + fix).
- One sentence per prose line.
- ASCII for path, flag, or before/after.
- File only on confirm.
- Lived issues only.
