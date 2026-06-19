# bugteam/scripts

Python scripts executed by the bugteam lead or teammates at runtime. These are not loaded into context as instructions — they run as subprocess calls from within the skill workflow.

## Scripts

| File | Purpose |
|---|---|
| `bugteam_preflight.py` | Run pytest and optional `pre-commit` before the first loop. Skips pytest when `BUGTEAM_PREFLIGHT_SKIP=1` or no test files exist. |
| `bugteam_fix_hookspath.py` | Auto-remediate a stale `core.hooksPath` override, set the canonical global value, re-run preflight. |
| `bugteam_code_rules_gate.py` | Run `validate_content` from `code_rules_enforcer.py` on PR-scoped files. Exit 1 on mandatory rule failures. |
| `grant_project_claude_permissions.py` | Grant Edit/Write/Read on `cwd/.claude/**` in `~/.claude/settings.json`. |
| `revoke_project_claude_permissions.py` | Remove the matching grant entries from `~/.claude/settings.json`. |
| `_bugteam_permissions_common.py` | Shared helpers for grant/revoke (atomic JSON writes, settings sections). |
| `windows_safe_rmtree.py` | Remove a directory tree on Windows by stripping ReadOnly attributes and retrying on failure. |
| `probe_code_rules_enforcer_check.py` | Load `code_rules_enforcer.py` and invoke a named check function against a fixture file. |
| `reflow_skill_md.py` | Reflow the bugteam SKILL.md body to fit line-length limits. |

## Test files

| File | Tests |
|---|---|
| `test_bugteam_preflight.py` | `bugteam_preflight.py` |
| `test_bugteam_code_rules_gate.py` | `bugteam_code_rules_gate.py` |
| `test_bugteam_fix_hookspath.py` | `bugteam_fix_hookspath.py` |
| `test_bugteam_permissions_common.py` | `_bugteam_permissions_common.py` |
| `test__bugteam_permissions_common.py` | Internal helpers in `_bugteam_permissions_common.py` |
| `test_agent_config_carveout.py` | `.claude/**` grant/revoke carveout logic |
| `test_probe_code_rules_enforcer_check.py` | `probe_code_rules_enforcer_check.py` |
| `test_windows_safe_rmtree.py` | `windows_safe_rmtree.py` |

## Subdirectories

| Directory | Role |
|---|---|
| `bugteam_scripts_constants/` | Named constants imported by the scripts above. |
