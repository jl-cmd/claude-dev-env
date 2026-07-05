# hooks/session

SessionStart and SessionEnd hooks for per-session setup and cleanup: removing stale directories at startup, pruning plugin data at shutdown, detecting unregistered repositories, and starting the session's task-list maintenance loop.

## Key files

| File | Event | What it does |
|---|---|---|
| `session_env_cleanup.py` | SessionStart | Removes the current session's pre-existing `~/.claude/session-env/<session_id>/` directory and prunes sibling entries older than the stale-age threshold. Prevents `EEXIST` errors from non-recursive `mkdir` calls in the Bash tool on Windows. |
| `gh_pr_author_session_cleanup.py` | SessionEnd | Clears any PR-author swap state left over from the current session |
| `session_edit_tracker_cleanup.py` | SessionStart, SessionEnd | Deletes the tracker file for the running Claude Code conversation from the system temp directory — at start for a clean slate and at end for a clean exit. A tracker is read only by the conversation that wrote it, so a live idle tracker is kept while a peer cleans up |
| `plugin_data_dir_cleanup.py` | SessionEnd | Prunes stale plugin data directories |
| `untracked_repo_detector.py` | SessionStart | Detects when the session cwd is inside a git repository that is not registered in `~/.claude/project-paths.json` and logs a warning |
| `task_list_loop_starter.py` | SessionStart | Emits an `additionalContext` directive telling Claude to keep the task list current on a 10-minute cadence, starting the loop skill when one is not already running. Writes nothing and runs no tools itself. |
| `test_gh_pr_author_session_cleanup.py` | — | Tests for `gh_pr_author_session_cleanup.py` |
| `test_session_edit_tracker_cleanup.py` | — | Tests for `session_edit_tracker_cleanup.py` |
| `test_session_env_cleanup.py` | — | Tests for `session_env_cleanup.py` |
| `test_untracked_repo_detector.py` | — | Tests for `untracked_repo_detector.py` |
| `test_task_list_loop_starter.py` | — | Tests for `task_list_loop_starter.py` |

## Conventions

- `session_env_cleanup.py` is Windows-specific in effect but safe to run on all platforms; it exits 0 when the target directory does not exist.
- Constants (stale-age threshold, directory names) live in `hooks_constants/session_env_cleanup_constants.py`.
- Tests run with `python -m pytest session/test_<name>.py`.
