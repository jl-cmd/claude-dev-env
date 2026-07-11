# recall

Retrieves prior session context and decisions from the Obsidian vault for the current project.

**Trigger:** `/recall [search query or project name]`.

## Purpose

Surfaces relevant session reports, decision notes, and research from the Obsidian vault before starting work. Prevents repeating decisions already made or missing known gotchas.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | The complete skill — six steps (resolve query, frontmatter search, content search, read top matches, present with attribution, handle no results). No companion files. |

## How the skill runs

1. Uses `$ARGUMENTS` as the search query, or infers the project name from conversation context.
2. Searches by frontmatter first (`mcp__obsidian__search_notes` with `searchFrontmatter: true`) to catch session reports and decision notes tagged with the project.
3. Falls back to content keyword search when frontmatter search returns few results.
4. Reads the top 3 most relevant notes via `mcp__obsidian__read_note`, preferring recent notes and decision summaries over raw research.
5. Reports each note with its path, date, relevant excerpts, and whether any decisions are marked `status: Superseded`.
6. States clearly when no vault history exists — never infers or invents history.

## Conventions

- `disable-model-invocation: true` is not set; this skill does invoke the model to synthesize results.
- The skill is read-only: it never writes to the vault.
- Companion to `/remember` (which writes decisions) and `/session-log` (which writes session reports).
