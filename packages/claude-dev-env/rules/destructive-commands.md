# Destructive Commands in Bash

No hook watches Bash commands for destructive patterns. What you face is the harness permission prompt. The harness raises it from the session permission mode and the permission rules in effect on your host. In a background or auto-mode run no human can answer that prompt, so the call stalls.

Two consequences follow. Use an allowed removal form, and keep a destructive literal out of the command string even when it rides only as data.

## Removal forms to prefer

- **Scratch and probe files.** Use the PowerShell tool with `Remove-Item -Recurse -Force -Confirm:$false <absolute path>`.
- **Worktrees.** Use `git worktree remove --force <path>`.
- **Tracked files.** Use `git rm <path>`, which records the deletion in the index.
- **Bash `rm` when unavoidable.** Write one standalone `rm` with absolute literal paths, no chaining, and no globs. Keep every target inside the ephemeral namespace below.

## The ephemeral namespace

Keep a Bash `rm` to targets that resolve inside one of these:

- The OS temporary root.
- A path rooted at `/tmp` or `/temp`, drive-letter tolerant.
- A path holding a `/worktrees/` or `/worktree/` segment, or a directory git reports inside a worktree admin directory.
- `~/.claude`.

Never pass a bare ephemeral root, such as `/tmp`, the OS temp root itself, or a bare directory named `worktrees` or `worktree`. A single stray argument then wipes the whole namespace.

Write each target as a literal path. A variable, a `$(...)` or backtick expansion, or a brace glob hides what the command will delete from the reader and from the permission matcher.

A file left in the OS temp directory or under `$CLAUDE_JOB_DIR` is cleaned by the harness and needs no explicit removal. See the exception clause in [`cleanup-temp-files.md`](cleanup-temp-files.md).

## Keep destructive literals out of the command string

The permission matcher reads the raw command string. A destructive literal carried only as data still sits in that string, so it can push the command out of an allowed shape and into a prompt even though the shell never executes it. This covers a commit message, a PR or issue body, an echoed string, a `python -c` or `node -e` or `awk` argument, and a heredoc.

- Bodies that describe destructive-command behavior go in a file passed by path, such as `git commit -F <file>` or `gh … --body-file <file>`. See [`gh-cli-conventions.md`](gh-cli-conventions.md). Never `git commit -m` or `gh … -b`.
- To exercise or verify a hook, run the committed test suite with `python -m pytest <test_file>`, which passes the command strings as in-language data. Never an inline `python -c` harness.

## Every subagent prompt carries the rule

A prompt-delivered directive reaches only the agent that gets it. An agent that spawns its own workers, such as review lenses, fix agents, or verifiers, copies this line into every subagent prompt it issues. A grandchild cleaning up its own probe file then uses an allowed form:

> Never use bash rm in any form. Delete scratch/probe files with the PowerShell tool (Remove-Item -Recurse -Force -Confirm:$false <absolute path>), or leave them in the OS temp dir; remove worktrees only via git worktree remove --force.

Prefer that a child leaves its scratch files for the parent to remove at teardown.

## Sibling rules

- [`cleanup-temp-files.md`](cleanup-temp-files.md) names which scratch files a task removes, and which it leaves.
- [`windows-filesystem-safe.md`](windows-filesystem-safe.md) holds the safe `rmtree` and `force_rmtree` patterns for read-only Windows files.
