# hooks/lifecycle

Hooks that run at session or config-change boundaries rather than on individual tool calls.

## Key files

| File | Event | What it does |
|---|---|---|
| `config_change_guard.py` | PostToolUse (Write/Edit on `settings.json`) | Counts hooks in the edited `settings.json` and logs any change to `~/.claude/cache/config-change-audit.log`; alerts when the hook count drops below the last known value |
| `pr_converge_bugteam_skill_tracker.py` | PostToolUse | Tracks which bugteam skill runs have completed within a pr-converge loop, so the enforcer can verify parallel execution |
| `session_end_cleanup.py` | SessionEnd | Purges stale cache entries from `~/.claude/cache/` (entries older than the configured threshold) and old backup files |
| `test_config_change_guard.py` | — | Tests for `config_change_guard.py` |
| `test_pr_converge_bugteam_skill_tracker.py` | — | Tests for `pr_converge_bugteam_skill_tracker.py` |

## Conventions

- Constants for these hooks (stale-age threshold, cache directory, known-hook-count file) live in `hooks_constants/session_env_cleanup_constants.py` and `hooks_constants/pr_converge_bugteam_enforcer_constants.py`.
- Tests run with `python -m pytest lifecycle/test_<name>.py`.
