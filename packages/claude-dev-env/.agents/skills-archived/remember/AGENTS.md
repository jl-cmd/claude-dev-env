# remember

Saves a decision, gotcha, or architectural choice to the Obsidian vault as a structured note.

**Trigger:** User-initiated only. `/remember [what to remember]`.

## Purpose

Writes a decision, fact, procedure, or gotcha to `decisions/[Project] - [Short Title].md` in the Obsidian vault. Each note carries structured frontmatter and a body shaped by its type, making it searchable and readable via `/recall`.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | The complete skill — six steps (parse input, classify type, infer project, generate title, write to vault, confirm). No companion files. |

## Four note types

| Type | Body format |
|---|---|
| `decision` | Decision + Reasoning + Alternatives + Consequences |
| `gotcha` | Gotcha + Symptom + Fix |
| `procedural` | 1–3 clear sentences describing the how-to |
| `fact` | 1–3 clear sentences stating the fact |

## Conventions

- `disable-model-invocation: true` is set — runs without a secondary LLM call.
- Writes via `mcp__obsidian__write_note` only; never edits existing notes.
- Path pattern: `decisions/[Project] - [Short Title].md`.
- Companion to `/recall` (reads vault) and `/session-log` (triggers decision extraction at session end).
