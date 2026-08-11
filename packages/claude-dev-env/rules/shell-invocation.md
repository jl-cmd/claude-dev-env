# Shell Invocation

Two constraints govern every shell command an agent issues: which shell runs it, and what the command string may contain.

## Use pwsh

Every Bash-tool shell command on Windows uses `pwsh`: `pwsh -NoProfile -File '<script>.ps1' <args>` for scripts, `pwsh -NoProfile -Command "..."` (or a literal `@'...'@` here-string) for inline work, or the built-in `PowerShell` tool for pure-PowerShell workflows (it supports `run_in_background`). Never wrap a script path in `-Command "& '...'"` — `-File` keeps `permissions.allow` matching. The `&` call operator is fine for invoking an executable at a path (`& '<venv>\Scripts\python.exe' script.py`).

The mandate covers the shell a command runs through, not every executable a command names. A direct interpreter invocation another rule documents — the paramiko NAS helper in [`nas-ssh-invocation.md`](nas-ssh-invocation.md), a `python` call on a repo script — conforms as written.

Keep `powershell`, `powershell.exe`, `cmd /c`, and `bash -c` out of the `settings.json` permission rules. `Audit-ShellPolicy.ps1` reports those forms and `Migrate-ShellPolicy.ps1` rewrites them to `pwsh`. Both ship in the claude-dev-env repo at `packages/claude-dev-env/scripts/` and run on demand, not as a live gate.

## No shell substitution

No `$(...)`, unescaped backticks, or `<(...)` / `>(...)` process substitution in Bash tool commands. The allowlist matcher reads the raw command string, so a substitution wrapper forces a permission prompt even when every inner segment is auto-allowed. Split into separate tool calls, or use flag forms like `git -C "<path>" rev-parse HEAD`. Arithmetic `$((...))` passes: it spawns no subshell.

When a script file's literal body needs `$(...)`, author it with the Write tool, not a Bash heredoc.

## Enforcement

`shell_substitution_blocker.py` (PreToolUse on Bash, hosted by `bash_pre_tool_use_dispatcher`) denies a command carrying a live substitution and returns the split-into-two-calls rewrite. Single-quoted runs are stripped before the scan, and a backtick preceded by an odd number of backslashes is escaped, so an inert mention passes.
