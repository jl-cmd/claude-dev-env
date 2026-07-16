# Deterministic skill elements

Source: [Anthropic — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) (scripts, progressive disclosure), [Lessons from Building Claude Code](thariq-x-post-skills.json), repo skill conventions (`skills/CLAUDE.md`), `docs/CODE_RULES.md`.

## Contents

- [Rule](#rule)
- [What counts as deterministic](#what-counts-as-deterministic)
- [Placement](#placement)
- [CODE_RULES bar (every code file in the skill)](#code_rules-bar-every-code-file-in-the-skill)
- [Inventory (required before Write)](#inventory-required-before-write)
- [Author checklist](#author-checklist)
- [Anti-patterns (fail self-audit)](#anti-patterns-fail-self-audit)
- [How the body should look](#how-the-body-should-look)
- [Relation to other skill-builder specs](#relation-to-other-skill-builder-specs)

## Rule

Any skill element that is **deterministic** ships as **code** (or a fixed artifact the code loads). It does not live only as prose steps, fenced source, or ad-hoc shell one-liners inside `SKILL.md`.

> "One of the most powerful tools you can give Claude is code — letting Claude spend its turns on composition rather than reconstructing boilerplate."

> "These can include deterministic scripts or tools for maximum robustness."

Judgment, routing, and refusal stay in markdown. Fixed procedures, checks, and transforms stay in scripts.

## What counts as deterministic

A process step is deterministic when **all** of these hold:

1. Same inputs → same outputs (no open-ended taste or design judgment).
2. Success or failure is machine-checkable (exit code, schema, path exists, token present).
3. A human could write the step as a pure function or a fixed command sequence.

### Deterministic (must be code or a fixed artifact)

| Shape | Home |
|---|---|
| Validators, linters, schema/packet checks | `scripts/` (or `workflow/*.mjs`) |
| Multi-step mechanical sequences (compile, collect, gate, scan) | `scripts/` |
| Detection logic (regex sets, path rules, pattern catalogs) | `scripts/` + `*_constants/` |
| Sorting, ranking, ID assignment, path resolution | `scripts/` |
| Verbatim prompt or output templates | `templates/` (skill body points to the path) |
| Long fixed checklists / tables Claude must follow exactly | `reference/` or a script that prints the list |
| Inline Python / JS fences meant to run | Extract to `scripts/` or `workflow/` |

### Judgment (markdown is correct)

| Shape | Home |
|---|---|
| When to invoke the skill; refusal lines | `SKILL.md` |
| How to weigh trade-offs or pick among valid approaches | `SKILL.md` / `reference/` |
| Gotchas and failure modes | `SKILL.md` |
| Sub-skill routing and composition | `SKILL.md` |
| Degree-of-freedom guidance | `SKILL.md` |

### Borderline

- A short `[ ]` checklist Claude ticks while **orchestrating** judgment steps → stays in body.
- A long checklist that **is** the work product or a gate Claude must not paraphrase → `reference/` or script.
- A one-liner that only launches a tool with no branching → may stay in body; the moment it grows patterns, branches, or magic strings → `scripts/`.

## Placement

| Artifact | Directory | Role |
|---|---|---|
| Python helpers | `scripts/` | Run, do not load into context as source |
| Workflow scripts | `workflow/` (`*.mjs`) | Host `Workflow` tool entrypoints |
| Named constants | `*_constants/` next to the scripts that import them | CODE_RULES config surface for skill code |
| Fixed templates | `templates/` | Copy/fill or pass to a script |
| Domain tables, long fixed lists | `reference/` | Load on demand |
| Process skeleton + pointers | `SKILL.md` | "Run `scripts/foo.py` …" / "Read `reference/bar.md` when …" |

`SKILL.md` names the script, when to run it, what it prints, and how to treat non-zero exit. It does not restate the algorithm.

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

For each process step:

| Column | Content |
|---|---|
| Step | Short name |
| Class | `deterministic` \| `judgment` \| `borderline` |
| Home | Path (`scripts/…`, `templates/…`, `reference/…`, or `SKILL.md`) |
| Evidence | Why this class (one line) |

Rules:

- Every `deterministic` row has a real file path under `scripts/`, `workflow/`, `templates/`, or `reference/` — not "inline in SKILL.md."
- Every code path under `scripts/` or `workflow/` has a paired test path listed (or a one-line reason it is pure data with no logic).
- A `borderline` row kept in prose has a one-line why it is not worth extracting.

## Author checklist

Copy into the Gather gate and check every box:

- [ ] Every process step is classified (deterministic / judgment / borderline).
- [ ] Every deterministic step has a script, workflow, template, or reference path — not prose-only.
- [ ] No fenced executable source lives only inside `SKILL.md` when it is meant to run.
- [ ] No multi-branch detection/validation logic lives only as an `rg`/`grep` one-liner in the body.
- [ ] Each script states execute vs read intent from the body.
- [ ] Each script uses a `*_constants/` (or equivalent) package for non-obvious literals.
- [ ] Each new script path has a paired test in the same delivery.
- [ ] SKILL.md process steps point at paths; they do not re-implement the script in markdown.

## Anti-patterns (fail self-audit)

- Full Python/JS program in a markdown code fence as the skill's real implementation.
- Giant shell one-liner with many alternations as the only form of a detector.
- 10+ step mechanical verification sequence written only as numbered markdown.
- "Deterministic" claim in prose with no executable path Claude can run.
- Script that dumps unhandled exceptions for Claude to interpret.
- Magic literals and unnamed thresholds inside skill scripts.
- New script with no paired test.

## How the body should look

**Good:**

```markdown
## Step 3: Validate packet

Run `scripts/validate_packet.py --packet <path>`.
- Exit 0 → continue.
- Exit 2 → fix listed paths, re-run (do not invent missing sections).
```

**Bad:**

```markdown
## Step 3: Validate packet

Check that README.md, packet.json, context/source-map.md, …
Also run compileall, then pytest --collect-only, then scan for …
(and three more mechanical steps only in prose)
```

## Relation to other skill-builder specs

| Spec | Concern |
|---|---|
| `progressive-disclosure.md` | Where files live and how the hub points to them |
| `skill-modularity.md` | One capability; compose peer skills by name |
| `description-field.md` | Frontmatter trigger catalog |
| **This file** | Which elements must be code, and the CODE_RULES bar for that code |

Progressive disclosure alone does not satisfy this file: moving a mechanical sequence into `reference/` as prose still fails when the sequence is deterministic — it belongs in `scripts/`.
