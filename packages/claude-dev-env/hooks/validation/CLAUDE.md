# hooks/validation

PostToolUse hooks that validate code quality after Claude writes or edits a file. Unlike the blocking hooks (which fire PreToolUse and can deny the write), these hooks run after the write and report errors that need a follow-up fix.

## Key files

| File | Event | What it does |
|---|---|---|
| `mypy_validator.py` | PostToolUse (Write/Edit on `.py` files) | Runs mypy on the written file and blocks (via PostToolUse block decision) when type errors are found — catches missing attributes, wrong signatures, type mismatches, and import errors |
| `hook_format_validator.py` | PostToolUse | Validates that a hook script's output JSON matches the expected Claude Code hook-output schema |
| `test_mypy_validator.py` | — | Tests for `mypy_validator.py` |

## Conventions

- `mypy_validator.py` resolves the project root via `CLAUDE_PROJECT_ROOT` or `git rev-parse --show-toplevel`.
- It works on both WSL and Windows.
- Constants (timeouts, max displayed errors) are inline in `mypy_validator.py`; longer tunables go in `hooks_constants/`.
- The `eval_*.txt` files in this directory are evaluation exports used during development — not runtime artifacts.
- Tests run with `python -m pytest validation/test_<name>.py`.
