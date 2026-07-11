# hooks/lifecycle

Hooks that run at session or config-change boundaries rather than on individual tool calls.

## Key files

| File | Event | What it does |
|---|---|---|
| `config_change_guard.py` | PostToolUse (Write/Edit on `settings.json`) | Counts hooks in the edited `settings.json` and logs any change to `~/.claude/cache/config-change-audit.log`; alerts when the hook count drops below the last known value |
| `enter_worktree_origin_prefetch.py` | PreToolUse (EnterWorktree) | Fetches origin's default branch before a worktree creation call, keeping the `refs/remotes/origin/<default-branch>` ref that `fresh` mode reads current; never blocks on fetch failure |
| `pr_converge_bugteam_skill_tracker.py` | PreToolUse (Skill) | Tracks which bugteam skill runs have completed within a pr-converge loop, so the enforcer can verify parallel execution |
| `session_end_cleanup.py` | SessionEnd | Purges stale cache entries from `~/.claude/cache/` (entries older than the configured threshold) and old backup files |
| `test_config_change_guard.py` | — | Tests for `config_change_guard.py` |
| `test_enter_worktree_origin_prefetch.py` | — | Tests for `enter_worktree_origin_prefetch.py` |
| `test_pr_converge_bugteam_skill_tracker.py` | — | Tests for `pr_converge_bugteam_skill_tracker.py` |

## Conventions

- Constants for these hooks (stale-age threshold, cache directory, known-hook-count file, EnterWorktree prefetch tuning) live in `hooks_constants/session_env_cleanup_constants.py`, `hooks_constants/pr_converge_bugteam_enforcer_constants.py`, and `hooks_constants/enter_worktree_prefetch_constants.py`.
- Tests run with `python -m pytest lifecycle/test_<name>.py`.
