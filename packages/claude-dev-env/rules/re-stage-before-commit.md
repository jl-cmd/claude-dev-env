# Re-Stage Session Edits Before Commit

**When this applies:** Any `git commit` run through the Bash tool in a git repository.

## Rule

Stage the files you edited this session right before you commit them. A file this session changed but left unstaged is dropped by a plain `git commit` — the commit records the staged snapshot and the edit stays behind in the working tree.

The `session_edit_stage_gate` hook holds you to this. It reads the per-session tracker that records every file the session edited, checks which of those files are tracked yet still unstaged at commit time, and denies the commit when any are left out. The denial names each file and gives the exact fix: `git add <paths>`, `git commit -a`, or a `# partial-commit` marker.

## What the gate allows

The gate steps aside for a commit that skips staged files on purpose:

- **`-a` / `--all`** — the commit already takes every tracked change, so nothing is dropped.
- **A pathspec** — `git commit -- <paths>` or `git commit <paths>` commits only the named paths on purpose.
- **`# partial-commit`** — add this marker to the command to commit the staged set on purpose and leave the rest.

A `--amend` does not step the gate aside: an amend records the staged snapshot too, so an unstaged session edit is dropped the same way a plain commit drops it.

A missing tracker file or any git failure allows the commit, so the gate never blocks on a tooling problem.

## Companion hooks

- `session_file_edit_tracker` (PostToolUse) records the resolved absolute path of each Write, Edit, and MultiEdit into the per-session tracker file.
- `session_edit_tracker_cleanup` (SessionStart) deletes the current session's tracker file and prunes stale tracker files left by crashed sessions.

## Why

A stale git index is a quiet failure: the commit succeeds, the branch looks right, and one file you meant to include never lands. Catching it at commit time keeps the staged set and the session's edits in step.
