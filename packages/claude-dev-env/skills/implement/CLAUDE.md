# Spec Execution Skill

This skill (`implement`) runs a spec end-to-end while maintaining a sidecar `implementation-notes.html` that records design decisions, deviations, tradeoffs, and open questions made during the build.

**Trigger:** `/implement [path-to-spec]`, "build out this plan and keep notes".

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Full workflow: resolve spec, run it, write notes via `append_note.py` |
| `packages/claude-dev-env/skills/implement/scripts/append_note.py` | CLI that creates or appends to `implementation-notes.html` |
| `packages/claude-dev-env/skills/implement/scripts/implement_scripts_constants/notes_constants.py` | Section slugs → headings and default filename |

## Subdirectories

| Directory | Role |
|---|---|
| `scripts/` | Python CLI and constants for the notes file |

## Conventions

- The spec is taken from `$ARGUMENTS` (path) or the most recent plan in conversation context. If neither is present, the skill asks via `AskUserQuestion`.
- Notes are appended as decisions are made — not batched at the end.
- The `append_note.py` CLI accepts `--section decisions|deviations|tradeoffs|questions`, `--about`, `--note`, and optionally `--file`. When `--file` is omitted, the script writes to `./implementation-notes.html`.
- `$CLAUDE_SKILL_DIR` is substituted by Claude Code at runtime so the bundled script is found regardless of the current working directory.
- The notes file structure must not be hand-edited — `append_note.py` locates sections by `<section id="...">` markers and the first `</ul>` after each.
