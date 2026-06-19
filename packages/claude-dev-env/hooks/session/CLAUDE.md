# hooks/session

SessionStart and SessionEnd hooks that manage per-session resources: cleaning up stale directories at startup and pruning plugin data at shutdown.

## Key files

| File | Event | What it does |
|---|---|---|
| `session_env_cleanup.py` | SessionStart | Removes the current session's pre-existing `~/.claude/session-env/<session_id>/` directory and prunes sibling entries older than the stale-age threshold. Prevents `EEXIST` errors from non-recursive `mkdir` calls in the Bash tool on Windows. |
| `gh_pr_author_session_cleanup.py` | SessionEnd | Clears any PR-author swap state left over from the current session |
| `plugin_data_dir_cleanup.py` | SessionEnd | Prunes stale plugin data directories |
| `untracked_repo_detector.py` | SessionStart | Detects when the session cwd is inside a git repository that is not registered in `~/.claude/project-paths.json` and logs a warning |
| `test_gh_pr_author_session_cleanup.py` | — | Tests for `gh_pr_author_session_cleanup.py` |
| `test_session_env_cleanup.py` | — | Tests for `session_env_cleanup.py` |
| `test_untracked_repo_detector.py` | — | Tests for `untracked_repo_detector.py` |

## Conventions

- `session_env_cleanup.py` is Windows-specific in effect but safe to run on all platforms; it exits 0 when the target directory does not exist.
- Constants (stale-age threshold, directory names) live in `hooks_constants/session_env_cleanup_constants.py`.
- Tests run with `python -m pytest session/test_<name>.py`.
