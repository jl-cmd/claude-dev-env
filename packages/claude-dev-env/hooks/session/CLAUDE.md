# hooks/session

SessionStart and SessionEnd hooks for per-session setup and cleanup: removing stale session and plugin-data directories at startup, detecting unregistered repositories, starting the session's task-list maintenance loop, and clearing PR-author swap state at shutdown.

## Key files

| File | Event | What it does |
|---|---|---|
| `session_env_cleanup.py` | SessionStart | Removes the current session's pre-existing `~/.claude/session-env/<session_id>/` directory and prunes sibling entries older than the stale-age threshold. Prevents `EEXIST` errors from non-recursive `mkdir` calls in the Bash tool on Windows. |
| `gh_pr_author_session_cleanup.py` | SessionEnd | Clears any PR-author swap state left over from the current session |
| `session_edit_tracker_cleanup.py` | SessionStart, SessionEnd | Deletes the tracker file for the running Claude Code conversation from the system temp directory — at start for a clean slate and at end for a clean exit. A tracker is read only by the conversation that wrote it, so a live idle tracker is kept while a peer cleans up |
| `plugin_data_dir_cleanup.py` | SessionStart | Removes empty plugin data directories at startup to prevent `EEXIST` when Claude Code recreates them |
| `untracked_repo_detector.py` | SessionStart | Detects when the session cwd is inside a git repository that is not registered in `~/.claude/project-paths.json` and logs a warning |
| `task_list_loop_starter.py` | SessionStart | Emits an `additionalContext` directive telling Claude to keep the task list current on a 10-minute cadence, starting the `/loop` skill when one is not already running. Writes nothing and runs no tools itself. |
| `test_gh_pr_author_session_cleanup.py` | — | Tests for `gh_pr_author_session_cleanup.py` |
| `test_session_edit_tracker_cleanup.py` | — | Tests for `session_edit_tracker_cleanup.py` |
| `test_session_env_cleanup.py` | — | Tests for `session_env_cleanup.py` |
| `test_untracked_repo_detector.py` | — | Tests for `untracked_repo_detector.py` |
| `test_task_list_loop_starter.py` | — | Tests for `task_list_loop_starter.py` |

| `_path_setup.py` | - | Inserts the hooks directory on `sys.path` so session entry-point hooks import `hooks_constants` with imports kept at module top. |
| `test__path_setup.py` | - | Tests for `_path_setup.py` |

| `orchestrator_auto_starter.py` | SessionStart | Injects a directive telling Claude to run `/orchestrator`, gated on an inject-eligible source and the `CLAUDE_AUTO_ORCHESTRATOR` toggle. Emits the nested SessionStart payload; stays silent on any failed gate. |
| `test_orchestrator_auto_starter.py` | - | Tests for `orchestrator_auto_starter.py` |

| `issue_tracker_session_starter.py` | SessionStart | Injects a directive telling Claude to start the issue-tracker skill or agent, gated on an inject-eligible source, the `CLAUDE_ISSUE_TRACKER` toggle, a GitHub origin remote, and tracker skill/agent files under `~/.claude`. |
| `test_issue_tracker_session_starter.py` | - | Tests for `issue_tracker_session_starter.py` |

## Conventions

- `session_env_cleanup.py` is Windows-specific in effect but safe to run on all platforms; it exits 0 when the target directory does not exist.
- Constants (stale-age threshold, directory names) live in `hooks_constants/session_env_cleanup_constants.py`.
- Tests run with `python -m pytest session/test_<name>.py`.
