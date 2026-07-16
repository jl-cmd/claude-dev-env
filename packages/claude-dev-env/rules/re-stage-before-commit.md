# Re-Stage Session Edits Before Commit

Stage the files you edited this session right before you commit them. A plain `git commit` records only the staged snapshot; a tracked file this session changed but left unstaged stays behind in the working tree.

`session_edit_stage_gate` (PreToolUse on Bash `git commit`) denies a commit that would drop tracked session edits and names the fix: `git add <paths>`, `git commit -a`, or a `# partial-commit` marker.

## Escapes the denial does not restate

- **A pathspec** — `git commit -- <paths>` or `git commit <paths>` commits only the named paths on purpose and steps the gate aside.
- **A preceding `git add` / `git stage`** — `git add <paths> && git commit …` stages the files in its own segment before the commit runs.

A `--amend` does not step the gate aside: an amend records the staged snapshot too, so an unstaged session edit is dropped the same way a plain commit drops it.

`session_file_edit_tracker` (PostToolUse) records each Write/Edit/MultiEdit path; `session_edit_tracker_cleanup` (SessionStart, SessionEnd) clears the session's tracker.
