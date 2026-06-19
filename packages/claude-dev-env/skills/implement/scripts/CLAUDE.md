# scripts (spec-build skill)

Support scripts for the spec-build (`implement`) skill. These scripts create and append to the `implementation-notes.html` sidecar file the skill maintains during a spec build.

## Key files

| File | Purpose |
|---|---|
| `append_note.py` | CLI that creates `implementation-notes.html` with four sections on first run and appends a `<li>` to a named section on later runs |
| `test_append_note.py` | Tests for `append_note.py` |

## Subdirectories

| Directory | Role |
|---|---|
| `implement_scripts_constants/` | Section slug → heading map and default filename constant |

## Conventions

- `append_note.py` imports section metadata from `implement_scripts_constants.notes_constants`.
- HTML-escaping of `--about` and `--note` is handled by the script; callers pass raw text.
- The script is invoked as `python "${CLAUDE_SKILL_DIR}/scripts/append_note.py"` from within the skill, where `$CLAUDE_SKILL_DIR` resolves to the installed skill directory at runtime.
