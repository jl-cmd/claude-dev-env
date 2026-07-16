# Shell Invocation Policy (pwsh-only)

Every Bash-tool shell command on Windows uses `pwsh`: `pwsh -NoProfile -File '<script>.ps1' <args>` for scripts, `pwsh -NoProfile -Command "..."` (or a literal `@'...'@` here-string) for inline work, or the built-in `PowerShell` tool for pure-PowerShell workflows (it supports `run_in_background`). Never wrap a script path in `-Command "& '...'"` — `-File` keeps `permissions.allow` matching. The `&` call operator is fine for invoking an executable at a path (`& '<venv>\Scripts\python.exe' script.py`).

Keep `powershell`, `powershell.exe`, `cmd /c`, and `bash -c` out of the `settings.json` permission rules. `Audit-ShellPolicy.ps1` reports those forms and `Migrate-ShellPolicy.ps1` rewrites them to `pwsh`, both in `packages/claude-dev-env/scripts/` and run on demand, not as a live gate.
