# hooks/git-hooks/git_hooks_constants

Shared constants imported by the git-hook scripts in `git-hooks/`. Centralizes exit codes, argument names, and error messages so every tunable lives in one place.

## Files

| File | Contents |
|---|---|
| `__init__.py` | Exports all constants; marks this as a package so `from git_hooks_constants import ...` resolves |

## Key constants (defined in `__init__.py`)

- `GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE` — exit code when the gate script cannot be found or launched
- `GATE_SCRIPT_NOT_FOUND_MESSAGE` — error message when the gate script path does not exist
- `INVOKE_GATE_FAILURE_MESSAGE` — error message when the gate subprocess fails to start
- `STAGED_SCOPE_ARGUMENT` — CLI argument passed to the gate script to scope it to staged changes

## Conventions

- Import with `from git_hooks_constants import <CONSTANT>` from within the `git-hooks/` directory.
- Add new constants here rather than inline in the hook scripts.
