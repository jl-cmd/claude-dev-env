# Re-Stage Session Edits Before Commit

Stage the files you edited this session right before you commit them. A plain `git commit` records only the staged snapshot; a tracked file this session changed but left unstaged stays behind in the working tree.

No hook denies a commit that would drop tracked session edits. Run `git status` before you commit, then stage what you changed with `git add <paths>` or commit with `git commit -a`.

Staging covers tracked files you edited. Do not commit untracked files unless the user explicitly instructs it. An untracked file in the working tree is outside the change until they say otherwise.

## Staging shapes

- **A pathspec.** `git commit -- <paths>` or `git commit <paths>` commits only the named paths on purpose.
- **A preceding `git add` or `git stage`.** `git add <paths> && git commit …` stages the files in its own segment before the commit runs.

A `--amend` carries the same risk. An amend records the staged snapshot too, so an unstaged session edit is dropped the same way a plain commit drops it.

`session_file_edit_tracker` (PostToolUse) still records each Write/Edit/MultiEdit path, and `session_edit_tracker_cleanup` (SessionStart, SessionEnd) still clears the session's tracker. No gate reads that record today, so it serves as history rather than a precondition.
