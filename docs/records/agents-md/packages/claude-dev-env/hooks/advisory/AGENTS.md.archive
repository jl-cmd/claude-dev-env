# hooks/advisory

Hooks that produce a warning prompt (`permissionDecision: "ask"`) rather than an outright block. The user sees the warning and can continue or cancel.

## Key files

| File | Event | What it guards |
|---|---|---|
| `migration_safety_advisor.py` | PreToolUse (Write/Edit) | Django migration files containing `RemoveField`, `RenameField`, `DeleteModel`, or `RenameModel` — warns that these operations must be backwards-compatible during deployment |
| `refactor_guard.py` | PreToolUse (Edit) | Edits that rename or restructure existing code not present in the current git diff — warns that the change may be out of scope |

## Conventions

- Both hooks exit 0 (silent) when their trigger condition is not met.
- `refactor_guard.py` respects a bypass token at `~/.claude/.refactor-bypass-token`; when that file exists the hook stays silent.
- Tests live beside each hook following the `test_<name>.py` pattern used in `blocking/`. Run with `python -m pytest <test_file>`.
