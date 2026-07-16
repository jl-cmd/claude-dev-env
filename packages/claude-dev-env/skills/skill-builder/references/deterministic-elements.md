# Deterministic skill elements

Source: [Anthropic — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) (scripts, progressive disclosure), [Lessons from Building Claude Code](thariq-x-post-skills.json), repo skill conventions (`skills/CLAUDE.md`), `docs/CODE_RULES.md`, host task tools (`TaskCreate`, `TodoWrite`, and equivalents).

## Contents

- [Rule](#rule)
- [What counts as deterministic](#what-counts-as-deterministic)
- [Placement](#placement)
- [Task-tool tracking (not markdown checklists)](#task-tool-tracking-not-markdown-checklists)
- [CODE_RULES bar (every code file in the skill)](#code_rules-bar-every-code-file-in-the-skill)
- [Inventory (required before Write)](#inventory-required-before-write)
- [Required task seeds (Gather / gates)](#required-task-seeds-gather--gates)
- [Anti-patterns (fail self-audit)](#anti-patterns-fail-self-audit)
- [How the body should look](#how-the-body-should-look)
- [Relation to other skill-builder specs](#relation-to-other-skill-builder-specs)

## Rule

Any skill element that is **deterministic** ships as **code**, a **fixed artifact**, or a **session task** — never as prose-only work tracking.

| Deterministic shape | Required home |
|---|---|
| Validators, transforms, detection, mechanical sequences | `scripts/` or `workflow/*.mjs` (+ tests, `*_constants/`) |
| Verbatim templates | `templates/` |
| Long fixed tables / catalogs Claude must not paraphrase | `reference/` |
| Ordered work the agent must complete without skipping | Host **task tool** (`TaskCreate`, `TodoWrite`, or equivalent) |

> "One of the most powerful tools you can give Claude is code — letting Claude spend its turns on composition rather than reconstructing boilerplate."

> "These can include deterministic scripts or tools for maximum robustness."

Judgment, routing, and refusal stay in markdown. Fixed procedures and transforms stay in scripts. Required step lists stay on the task list — not as markdown `[ ]` boxes.

## What counts as deterministic

A process step is deterministic when **all** of these hold:

1. Same inputs → same outputs (no open-ended taste or design judgment).
2. Success or failure is machine-checkable (exit code, schema, path exists, token present, task marked complete with evidence).
3. A human could write the step as a pure function, a fixed command sequence, or a fixed task list.

### Deterministic (must leave prose-only tracking)

| Shape | Home |
|---|---|
| Validators, linters, schema/packet checks | `scripts/` (or `workflow/*.mjs`) |
| Multi-step mechanical sequences (compile, collect, gate, scan) | `scripts/` |
| Detection logic (regex sets, path rules, pattern catalogs) | `scripts/` + `*_constants/` |
| Sorting, ranking, ID assignment, path resolution | `scripts/` |
| Verbatim prompt or output templates | `templates/` (skill body points to the path) |
| Long fixed tables / catalogs | `reference/` or a script that prints the list |
| Inline Python / JS fences meant to run | Extract to `scripts/` or `workflow/` |
| Ordered gates, audits, author checks the agent must finish | **Task tool** — seed each item; mark complete with evidence |

### Judgment (markdown is correct)

| Shape | Home |
|---|---|
| When to invoke the skill; refusal lines | `SKILL.md` |
| How to weigh trade-offs or pick among valid approaches | `SKILL.md` / `reference/` |
| Gotchas and failure modes | `SKILL.md` |
| Sub-skill routing and composition | `SKILL.md` |
| Degree-of-freedom guidance | `SKILL.md` |

### Borderline

- A one-liner that only launches a tool with no branching → may stay in body; the moment it grows patterns, branches, or magic strings → `scripts/`.
- A short narrative process outline (Step 1 / Step 2 headings) may stay in body **if** every required work item is also registered on the task list. Headings are orientation; the task list is the completion surface.
- Markdown `[ ]` as the only place an agent is expected to track progress → **always fail** when a task tool is available.

## Placement

| Artifact | Directory / surface | Role |
|---|---|---|
| Python helpers | `scripts/` | Run, do not load into context as source |
| Workflow scripts | `workflow/` (`*.mjs`) | Host `Workflow` tool entrypoints |
| Named constants | `*_constants/` next to the scripts that import them | CODE_RULES config surface for skill code |
| Fixed templates | `templates/` | Copy/fill or pass to a script |
| Domain tables, long fixed lists | `reference/` | Load on demand |
| Required work items | Host task tool | Create at skill start; complete with evidence |
| Process skeleton + pointers | `SKILL.md` | "Run `scripts/foo.py` …" / "Register tasks from …" |

`SKILL.md` names the script, when to run it, what it prints, and how to treat non-zero exit. It does not restate the algorithm. It names which task-seed lists to load and when to register them.

## Task-tool tracking (not markdown checklists)

Harnesses expose task tools so agents cannot silently skip steps. A skill that expects the agent to finish an ordered set of work **must**:

1. Publish the items as a **task seed list** (plain bullets or numbered lines in a reference file — **no** `- [ ]` syntax).
2. Instruct the agent, at the start of that phase, to **create one session task per item** via the host tool:
   - Prefer `TaskCreate` (or host `Task` / tasks MCP) when present.
   - Else `TodoWrite` / equivalent.
   - Fail closed: if no task tool exists, say so and stop — do not fall back to markdown checkboxes as the tracking plan.
3. Require each task to be marked complete only with evidence (PASS / FAIL+file:line / N/A+reason / exit code / path).
4. Ban "copy this checklist into your response and check it off" as the primary tracking method.

Reference files may still **catalog** the required items so authors and agents know what to seed. Catalogs are data for `TaskCreate`; they are not the live work board.

### Skills that ship multi-step process

Any skill whose process has two or more required steps must include a short **Task seeding** instruction in `SKILL.md` or the active workflow:

```markdown
## Task seeding

Before Step N, register every item under [reference/…-tasks.md] as a session task
(TaskCreate / TodoWrite). Work only from the task list. Mark complete with evidence.
```

The seed list file lives under `reference/` (or is a named section of an existing reference). Do not use `- [ ]` in that file.

## CODE_RULES bar (every code file in the skill)

Skill scripts are production code. They obey the same rules as the rest of the repo (`docs/CODE_RULES.md` / root `AGENTS.md`), including:

- **Named constants** — no bare magic numbers/strings in function bodies; skill-local values live in a `*_constants/` package the script imports.
- **Types** — parameters and returns annotated; no bare `Any` / untyped escape hatches.
- **Naming** — full words; `is_`/`has_` booleans; `all_` collections; `each_` multi-letter loops; banned prefixes (`handle_`, `process_`, `manage_`, `do_`).
- **Errors** — catch specific exceptions; exit with a clear code and message; do not punt raw traces to Claude as the recovery plan.
- **Tests** — every new production path ships a paired test in the same change (`test_*.py` beside the script, or `*.test.mjs` for workflow helpers).
- **Execute intent** — body says `Run scripts/…` (execute), not "see the script for the algorithm," unless the script is deliberately reference-only.

JS/TS skill helpers follow the same spirit: named constants, no silent stubs, paired tests.

## Inventory (required before Write)

Every new skill and every improve pass that touches process steps records a **deterministic elements inventory** in the gap analysis:

| Column | Content |
|---|---|
| Step | Short name |
| Class | `deterministic` \| `judgment` \| `borderline` |
| Home | Path (`scripts/…`, `workflow/…`, `templates/…`, `reference/…`, `task-seed:…`, or `SKILL.md`) |
| Evidence | Why this class (one line) |
| Paired test | Path if code; `task-tool` if work list; N/A + reason if pure judgment |

Rules:

- Every `deterministic` row has a real path under `scripts/`, `workflow/`, `templates/`, `reference/`, or a `task-seed:` pointer — not prose-only.
- Every code path under `scripts/` or `workflow/` has a paired test path (or a one-line pure-data reason).
- Every required multi-step work list has a `task-seed:` home and a body instruction to register those tasks.
- A `borderline` row kept in prose has a one-line why it is not worth extracting.

## Required task seeds (Gather / gates)

At the **deterministic-elements gate** (and again at self-audit), register **each** line below as its own session task, then complete it with evidence. Do not track these as markdown checkboxes.

1. Every process step is classified (deterministic / judgment / borderline).
2. Every deterministic step has a script, workflow, template, reference, or task-seed path — not prose-only.
3. No fenced executable source lives only inside `SKILL.md` when it is meant to run.
4. No multi-branch detection/validation logic lives only as an `rg`/`grep` one-liner in the body.
5. Each script states execute vs read intent from the body.
6. Each script uses a `*_constants/` (or equivalent) package for non-obvious literals.
7. Each new script path has a paired test in the same delivery.
8. `SKILL.md` process steps point at paths; they do not re-implement the script in markdown.
9. Every required multi-step work list in the skill is a task-seed catalog plus a seed instruction — not a markdown `- [ ]` board.

## Anti-patterns (fail self-audit)

- Full Python/JS program in a markdown code fence as the skill's real implementation.
- Giant shell one-liner with many alternations as the only form of a detector.
- 10+ step mechanical verification sequence written only as numbered markdown with no script.
- "Deterministic" claim in prose with no executable path Claude can run.
- Script that dumps unhandled exceptions for Claude to interpret.
- Magic literals and unnamed thresholds inside skill scripts.
- New script with no paired test.
- Markdown `- [ ]` checklist as the agent's progress tracker when a task tool is available.
- "Copy this checklist into your response and check off items" as the skill's completion protocol.
- Task-seed list written with checkbox syntax (`- [ ]`) so agents tick markdown instead of creating tasks.

## How the body should look

**Good (script):**

```markdown
## Step 3: Validate packet

Run `scripts/validate_packet.py --packet <path>`.
- Exit 0 → continue.
- Exit 2 → fix listed paths, re-run (do not invent missing sections).
```

**Good (required work list):**

```markdown
## Task seeding

Before self-audit, register every item in `reference/self-audit-tasks.md`
as a session task (TaskCreate). Complete each with PASS / FAIL+evidence / N/A+reason.
```

**Bad:**

```markdown
## Step 3: Validate packet

Check that README.md, packet.json, context/source-map.md, …
Also run compileall, then pytest --collect-only, then scan for …
(and three more mechanical steps only in prose)

## Self-audit

Copy this checklist into your response and check every box:
- [ ] Item one
- [ ] Item two
```

## Relation to other skill-builder specs

| Spec | Concern |
|---|---|
| `progressive-disclosure.md` | Where files live and how the hub points to them |
| `skill-modularity.md` | One capability; compose peer skills by name |
| `description-field.md` | Frontmatter trigger catalog |
| **This file** | Which elements must be code, task-tool lists, or fixed artifacts |

Progressive disclosure alone does not satisfy this file: moving a mechanical sequence into `reference/` as prose still fails when the sequence is deterministic — it belongs in `scripts/` or on the task list.
