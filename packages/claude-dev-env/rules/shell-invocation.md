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

One PreToolUse hook does run on a Bash command, and it only rewrites. `blocking/msys_rev_path_rewriter.py` (PreToolUse on Bash, hosted by `bash_pre_tool_use_dispatcher`) reads a git command before it runs and keeps Git Bash from converting a `<rev>:<path>` argument. That roster holds this one hook, and a test asserts its whole content, so a blocking hook added beside it fails the suite.

Git Bash rewrites that argument when the revision holds a slash and the path after the colon starts with a slash or a dot. It turns the colon into a semicolon and the slashes into backslashes, so `git show origin/main:.claude/settings.json` reaches git as `origin\main;.claude\settings.json` and git reports a revision that does not exist. A leading dot on a file is enough. `origin/main:.gitignore` reaches git as `origin\main;.gitignore`. `git show origin/main:packages/app.py` passes through untouched, and so does any path after the colon that starts with `./`, `../`, or `~/`. A revision without a slash, such as `HEAD:.claude/settings.json`, passes through too.

On that shape the rewriter names only the arguments it found, so `git show origin/main:.claude/settings.json` runs as:

```
export MSYS2_ARG_CONV_EXCL='origin/main:'; git show origin/main:.claude/settings.json
```

`MSYS2_ARG_CONV_EXCL` takes a semicolon-separated list of argument prefixes. Naming one prefix per detected token leaves every other argument in the command converting as before. The blanket pair `MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'` turns conversion off for the whole command, which changes a path the command meant to convert, so the rewriter does not emit it.

A quoted token is not a revision. `git commit -m "fix a/b:.py"` carries a slash and a dot in one token, and a rewrite there would break the message, so the detection skips a token holding whitespace or a quote.

`advisory/msys_path_conversion_advisor.py` (PostToolUse on Bash, hosted by `bash_post_call_dispatcher`) stays behind it. It reads a failed git call, looks for the mark MSYS leaves, and names the fix. It covers a shape the rewriter misses.
