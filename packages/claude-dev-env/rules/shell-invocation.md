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

No PreToolUse hook denies a Bash command. Commit `0f21faf8e` retired the blocking policy hooks and left the Bash PreToolUse roster empty. `shell_substitution_blocker.py` was one of them. The substitution constraint above is guidance a reader follows, and a permission prompt on a wrapped command is the signal that one slipped through.

One hook does cover a Bash command, and it runs after the call rather than before it. `advisory/msys_path_conversion_advisor.py` (PostToolUse on Bash, hosted by `bash_post_call_dispatcher`) reads a failed git call and looks for the mark MSYS leaves on a `<rev>:<path>` argument.

Git Bash rewrites that argument when the revision holds a slash and the path after the colon starts with a slash or a dot-directory name such as `.claude/`. It turns the colon into a semicolon and the slashes into backslashes, so `git show origin/main:.claude/settings.json` reaches git as `origin\main;.claude\settings.json` and git reports a revision that does not exist. `git show origin/main:packages/app.py` passes through untouched, and so does any path after the colon that starts with `./`, `../`, or `~/`.

On the rewritten shape the hook names the two exports that turn path conversion off:

```
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
```

Put that export and the git command in one command. The hook never blocks, so the advice lands on the first failure.
