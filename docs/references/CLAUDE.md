# docs/references/

Deep-reference material that informs architectural decisions in this repo.

## Purpose

Stores external articles, PDFs, and internal design documents that explain the
reasoning behind key systems. Files here are **read-only references** — do not
edit third-party content.

## Files

| File | Role |
|------|------|
| `skill-install-system.md` | Internal design doc: how skills, rules, hooks, and config travel from `packages/claude-dev-env/` to `~/.claude/` via the install pipeline. **Read this before adding a skill or changing install behavior.** |
| `anthropic-harnessing-claudes-intelligence-technique-inventory.md` | Inventory of prompting and agentic techniques from Anthropic research. |
| `bdd in action.pdf` | BDD reference material. |
| `Thariq on X_ _Lessons from Building Claude Code_...html` | Archived X post: lessons from building Claude Code, covering skill design. |
| `Thariq on X_ _Using Claude Code_ The Unreasonable Effectiveness of HTML_...html` | Archived X post: using Claude Code with HTML-centric workflows. |

## Conventions

- Add files here when they give lasting architectural guidance, not temporary planning notes.
- Planning notes belong in `docs/plans/` (not committed to the published package).
- Each HTML archive has a companion `*_files/` directory holding its assets; treat them as a unit.
