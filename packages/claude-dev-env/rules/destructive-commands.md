# Destructive Commands in Bash

The `destructive_command_blocker` PreToolUse hook watches every Bash-tool command and matches destructive patterns (`rm -rf`, `git reset --hard`, `dd`, `mkfs`, `chmod -R`, fork bombs) as raw text, with no quote-awareness. Anything it cannot prove safe falls through to a confirmation prompt. In a background or auto-mode run no human can answer that prompt, so the call stalls.

Two consequences follow: use an allowed removal form, and keep a destructive literal out of the command string even when it rides only as data.

## Removal forms that never prompt

- **Scratch and probe files** — the PowerShell tool: `Remove-Item -Recurse -Force -Confirm:$false <absolute path>`. The hook watches only the Bash tool, so a PowerShell removal never reaches it.
- **Worktrees** — `git worktree remove --force <path>`. This matches no destructive pattern.
- **Tracked files** — `git rm <path>`, which records the deletion in the index.
- **Bash `rm` when unavoidable** — one standalone `rm`, absolute literal paths, no chaining, no globs, every target inside the ephemeral namespace below.

## The ephemeral namespace the hook auto-allows

An `rm` is auto-allowed when it is a single invocation and every target resolves inside one of:

- The OS temporary root (`tempfile.gettempdir()`).
- A path rooted at `/tmp` or `/temp`, drive-letter tolerant.
- A path holding a `/worktrees/` or `/worktree/` segment, or a directory git reports inside a worktree admin directory.
- `~/.claude`.

A bare ephemeral root (`/tmp`, the OS temp root itself, a bare directory named `worktrees` or `worktree`) is refused, so a single stray argument cannot wipe the whole namespace.

Four environment variables resolve inside a target token: `TEMP`, `TMP`, `TMPDIR`, and `CLAUDE_JOB_DIR`. Any other variable, a `$(...)` or backtick expansion, or a brace glob makes the target unresolvable and the command prompts. A `$CLAUDE_JOB_DIR` path is auto-allowed only when it resolves into the namespace above — the variable is readable, not a blanket pass. Set `CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW` to a truthy value to turn the whole auto-allow off.

A file left in the OS temp directory or under `$CLAUDE_JOB_DIR` is cleaned by the harness and needs no explicit removal — see the exception clause in [`cleanup-temp-files.md`](cleanup-temp-files.md).

## Keep destructive literals out of the command string

A destructive literal carried only as data — a commit message, a PR or issue body, an echoed string, a `python -c` / `node -e` / `awk` argument, a heredoc — trips the same raw-text match even though the shell never executes it.

- Bodies that describe destructive-command behavior go in a file passed by path: `git commit -F <file>`, `gh … --body-file <file>` (see [`gh-cli-conventions.md`](gh-cli-conventions.md)). Never `git commit -m` or `gh … -b`.
- To exercise or verify the blocker, or any hook, run the committed test suite (`python -m pytest <test_file>`), which passes the command strings as in-language data. Never an inline `python -c` harness.

## Every subagent prompt carries the rule

A prompt-delivered directive reaches only the agent that gets it. An agent that spawns its own workers — review lenses, fix agents, verifiers — copies this line into every subagent prompt it issues, so a grandchild cleaning up its own probe file uses an allowed form:

> Never use bash rm in any form. Delete scratch/probe files with the PowerShell tool (Remove-Item -Recurse -Force -Confirm:$false <absolute path>), or leave them in the OS temp dir; remove worktrees only via git worktree remove --force.

Prefer that a child leaves its scratch files for the parent to remove at teardown.

## Sibling rules

- [`cleanup-temp-files.md`](cleanup-temp-files.md) — which scratch files a task removes, and which it leaves.
- [`windows-filesystem-safe.md`](windows-filesystem-safe.md) — the safe `rmtree` / `force_rmtree` patterns for read-only Windows files.
