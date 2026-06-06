# Shell Invocation Policy (pwsh-only)

Every Bash-tool shell command on Windows uses `pwsh`: `pwsh -NoProfile -File '<script>.ps1' <args>` for scripts, `pwsh -NoProfile -Command "..."` (or a literal `@'...'@` here-string) for inline work, or the built-in `PowerShell` tool for pure-PowerShell workflows (it supports `run_in_background`). Never wrap a script path in `-Command "& '...'"` — `-File` keeps `permissions.allow` matching. The `&` call operator is fine for invoking an executable at a path (`& '<venv>\Scripts\python.exe' script.py`).

`powershell`, `powershell.exe`, `cmd /c`, and `bash -c` are blocked by `permissions.deny` and the `pwsh_enforcer.py` PreToolUse hook, which returns the corrective pattern. Audit and migration scripts (`Audit-ShellPolicy.ps1`, `Migrate-ShellPolicy.ps1`) live in `packages/claude-dev-env/scripts/`.
