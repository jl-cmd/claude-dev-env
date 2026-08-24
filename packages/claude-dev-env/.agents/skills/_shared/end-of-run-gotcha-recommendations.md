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

1. Show findings in chat; categorize as P0-P3.
2. Then `AskUserQuestion`.
3. On confirm only, file via `issue-tracker`.

### Cold-reader frame

Assume zero context.

**Exactly two setup sentences**, each on its **own rendered line**:

1. What we were doing.
2. Why these notes matter.

### 1. Chat findings (always first)

#### Sentence law (HARD)

| Rule | Required |
|---|---|
| **One sentence per rendered line** | Exactly one terminal `.` `?` or `!` on that line |
| **No collapsed pairs** | A single markdown newline is **not** a line break — it joins sentences |
| **Force the break** | Blank line between every prose sentence, **or** one list item per sentence |
| **No clause glue** | No em-dash or semicolon joining two clauses |
| **One idea** | If you can split it, split it |
| **Heavy detail** | Prefer an **ASCII infographic** over a stack of sentences |

**Self-check before send:** paste the chat into a viewer that collapses soft breaks.

If two periods appear on one visual line, **split or diagram**.

#### Per gotcha (HARD shape)

| Part | Form |
|---|---|
| **Title** | Heading fragment only |
| **Broke** | One sentence alone on its rendered line |
| **Fix** | One sentence alone on its rendered line |
| **ASCII** | Required for path, flag, or before/after |

**Cap: two prose sentences per gotcha.**

```markdown
## Session close-out

We built phone-theme prompts from a project style catalog.

Keep these traps for the next run.

## Gotcha recommendations

### Wrong catalog folder

The style picker failed outside the project.

Run from the project root with data/midjourney_sref_catalog.json.

```text
wrong folder --> fail
project root --> data/midjourney_sref_catalog.json
```
```

**Wrong (soft break joins sentences into one line):**

```markdown
The style picker failed outside the project.
Run from the project root with data/midjourney_sref_catalog.json.
```

Renders as one line with **two** sentences.

**Right (blank line forces two lines):**

```markdown
The style picker failed outside the project.

Run from the project root with data/midjourney_sref_catalog.json.
```

**Right (list items):**

```markdown
- The style picker failed outside the project.
- Run from the project root with data/midjourney_sref_catalog.json.
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

## Built-in skill gotcha

**Two sentences on one rendered line.**

Markdown soft-breaks join prose.

Review the close-out before send.

Split with a blank line or a list item.

Or move the detail into an ASCII infographic.

## Rules

- Cold-reader first.
- Chat first, then ask.
- One sentence per **rendered** line.
- Blank line or list item between prose sentences.
- Two prose sentences per gotcha max.
- ASCII for path, flag, or before/after.
- File only on confirm.
- Lived issues only.
