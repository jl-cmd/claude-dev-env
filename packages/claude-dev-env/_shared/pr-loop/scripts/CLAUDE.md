# _shared/pr-loop/scripts

Python scripts invoked at runtime by the PR-loop skills. Each script is a standalone CLI entry point; `pr_loop_shared_constants/` holds the named constants they import.

## Key scripts

| File | Purpose |
|---|---|
| `preflight.py` | Pre-flight check run before each audit loop tick: verifies hooks path, finds test files, runs pytest, checks for `BUGTEAM_PREFLIGHT_SKIP` opt-out |
| `preflight_self_heal.py` | Clears stale `core.hooksPath` overrides that Git seeds into fresh worktree local config; called from `preflight.py` |
| `post_audit_thread.py` | Posts an audit review (APPROVE / REQUEST_CHANGES) to a draft PR via the GitHub reviews API; reads the body skeleton from `audit-reply-template.md` at runtime |
| `grant_project_claude_permissions.py` | Writes idempotent allow-rules and `additionalDirectories` entries into `~/.claude/settings.json` so subagents can edit the project's `.claude/` tree without prompting |
| `revoke_project_claude_permissions.py` | Removes the allow-rules and entries that `grant_project_claude_permissions.py` wrote; safe to run when no prior grant exists |
| `code_rules_gate.py` | Pre-commit gate that runs `code_rules_enforcer` checks on staged Python files before a fix commit lands |
| `reviews_disabled.py` | Shared helper for the `CLAUDE_REVIEWS_DISABLED` opt-out gate; parses the env-var token to find which reviewer types are suppressed |
| `fix_hookspath.py` | Repairs a malformed `core.hooksPath` global git config entry |
| `_claude_permissions_common.py` | Internal helpers shared by the grant/revoke scripts: atomic settings.json writes, list mutation, path helpers |

## Subdirectories

| Entry | Description |
|---|---|
| `pr_loop_shared_constants/` | Named constants used by the scripts above |
| `tests/` | pytest suite for all scripts in this directory |

## Running tests

```bash
python -m pytest packages/claude-dev-env/_shared/pr-loop/scripts/tests/
```
