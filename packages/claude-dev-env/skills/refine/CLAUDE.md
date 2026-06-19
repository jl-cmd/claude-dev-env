# refine

Interview-driven plan refiner with a built-in audit loop: fans out research agents, interviews via `AskUserQuestion`, writes the plan to the Obsidian vault, then loops audit and fix until clean.

**Trigger:** `/refine`, "refine this", "turn this into a plan", "flesh this out", "make a spec for this", "let's plan this out".

## Purpose

Walks a half-formed plan to a complete, audited implementation spec. The output always lands in the Obsidian vault at `Research/<topic>/<slug>.md`. The interview step is mandatory and cannot be suppressed by autonomous-mode or no-clarifying-questions directives.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Hub — 10-step process, gotchas, constraints, file index |
| `templates/plan-template.md` | Required structure for the written plan (YAML frontmatter + H1 + sections) |
| `templates/implementation-notes-template.html` | Skeleton the fix agent appends to during the audit-fix loop |

## Subdirectories

| Directory | Purpose |
|---|---|
| `templates/` | Output structures for the plan and the iteration notes file |

## Ten-step process (summary)

1. Resolve the topic (from `$ARGUMENTS`, file path, or conversation)
2. Layered fan-out via Explore agent (vault + repo + draft)
3. Existing-match decision (refine a prior plan or start fresh)
4. Interview loop via `AskUserQuestion` (mandatory, never skipped)
5. Confirm slug and path (`Research/<topic>/<slug>.md`)
6. Write the plan inline via `mcp__obsidian__write_note`
7. First audit via `general-purpose` agent (plan-quality rubric, not code rubric)
8. Audit-fix loop (up to 10 iterations; fix agent appends to HTML notes file)
9. Halt and surface open findings if cap reached
10. Report vault path, iteration count, and notes-file path

## Conventions

- Output goes to the Obsidian vault only — never to `docs/plans/`, `.claude/plans/`, or the cwd.
- HTML notes file (`<slug>-implementation-notes.html`) is append-only; each iteration adds one `<section>`.
- Slug and topic must match `^[a-z0-9-]+$`; path separators and uppercase letters are rejected.
- `Research/` prefix is fixed and cannot be overridden by a local plans folder.
- Audit uses `general-purpose` — not `code-quality-agent` or `clean-coder`, which target source code.
