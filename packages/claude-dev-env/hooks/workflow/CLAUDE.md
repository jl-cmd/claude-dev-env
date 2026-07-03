# hooks/workflow

PostToolUse hooks that trigger side-effects after Claude writes a file. They do not block writes; they produce companion artifacts automatically.

## Key files

| File | Event | What it does |
|---|---|---|
| `auto_formatter.py` | PostToolUse (Write/Edit) | Runs the project's auto-formatter (ruff, prettier, etc.) on the written file and sends a desktop notification when formatting changes are applied |
| `investigation_tracker_reset.py` | PostToolUse | Resets the investigation tracker state after a tool call |
| `test_auto_formatter.py` | — | Tests for `auto_formatter.py` |

## Conventions

- `auto_formatter.py` exits 0 even on failure — it logs warnings to stderr but does not break Claude's flow.
- Tests run with `python -m pytest workflow/test_<name>.py`.
