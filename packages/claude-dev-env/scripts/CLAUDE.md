# scripts

Utility scripts installed into `~/.claude/scripts/` by `bin/install.mjs`. Each script is a standalone tool a user or hook can invoke directly.

## Scripts

| File | Purpose |
|---|---|
| `setup_project_paths.py` | One-time bootstrap: discovers git repos via `es.exe` (Everything) and writes `~/.claude/project-paths.json`; never hardcodes scan roots |
| `sweep_empty_dirs.py` | Deletes empty directories older than a configurable age under a given root; runs once (`--once`) or in continuous-watch mode |
| `sync_to_cursor.py` | Entry point for syncing Claude rules to Cursor `.mdc` files; delegates to the `sync_to_cursor/` package |

## PowerShell scripts

| File | Purpose |
|---|---|
| `Audit-ShellPolicy.ps1` | Audits Bash tool calls in session transcripts against the `pwsh`-only shell policy |
| `Migrate-ShellPolicy.ps1` | Applies automated fixes for common shell-policy violations found by the audit script |
| `Install-SweepEmptyDirs.ps1` | Registers `sweep_empty_dirs.py` as a scheduled task on Windows |
| `check.ps1` | Runs the full code-quality check suite |

## Subdirectories

| Entry | Description |
|---|---|
| `dev_env_scripts_constants/` | Named constants (`timing.py`) for scripts in this directory |
| `sync_to_cursor/` | Package that builds Cursor `.mdc` files from Claude rules and docs |
| `tests/` | pytest suite for the Python scripts in this directory |

## Running tests

```bash
python -m pytest packages/claude-dev-env/scripts/tests/
```
