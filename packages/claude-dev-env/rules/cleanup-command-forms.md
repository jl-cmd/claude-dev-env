# Cleanup Command Forms

Never use bash `rm` in any form to clean up. The `destructive_command_blocker` hook watches every Bash-tool command and matches `rm -rf` (and the rest of the destructive patterns) as raw text. It auto-allows only a single standalone `rm` whose every target is an absolute literal path inside an ephemeral directory (the OS temp root, `/tmp`, `/temp`, or a worktrees directory). It falls through to a permission prompt on any other shape: a compound command (`cd <dir> && rm -rf <dir>`, `… ; rm -rf …`, a pipe, a backtick, `$(...)`), a `$` variable that could expand to a wider path, a relative target, a glob basename, or a string-executing wrapper (`bash -c 'rm -rf …'`). In a background or auto-mode run no human can answer that prompt, so the call stalls.

Remove files with these forms, which the hook never prompts on:

- **Scratch and probe files:** the PowerShell tool — `Remove-Item -Recurse -Force -Confirm:$false <absolute path>`. The hook watches only the Bash tool, so a PowerShell removal never reaches it. A file left in the OS temp dir or `$CLAUDE_JOB_DIR/tmp` is ephemeral and needs no explicit removal.
- **Worktrees:** `git worktree remove --force <path>`. This matches no destructive pattern.
- **When bash `rm` is unavoidable:** one standalone `rm` command, an absolute literal path under the OS temp root or a worktrees directory, no chaining, no variables, no globs. This is the one shape the hook auto-allows.

## Every subagent prompt carries the rule

A prompt-delivered directive reaches only the agent that gets it. An agent that spawns its own workers — review lenses, fix agents, verifiers — copies this line into every subagent prompt it issues, so a grandchild cleaning up its own probe file uses an allowed form:

> Never use bash rm in any form. Delete scratch/probe files with the PowerShell tool (Remove-Item -Recurse -Force -Confirm:$false <absolute path>) or the OS temp dir; remove worktrees only via git worktree remove --force.

Prefer that a child leaves its scratch files in place for the parent to remove at teardown with `Remove-Item`.

## Sibling rules

- [`no-inline-destructive-literals`](no-inline-destructive-literals.md) — keep a destructive literal out of the Bash command string even when it rides only as data.
- [`cleanup-temp-files`](cleanup-temp-files.md) — remove the scratch files a task created once the task is done.
- [`windows-filesystem-safe`](windows-filesystem-safe.md) — the safe `Remove-Item` / `rmtree` patterns for read-only Windows files.
