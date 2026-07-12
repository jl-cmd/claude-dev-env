# bugteam/scripts

Python scripts executed by the bugteam lead or teammates at runtime. These are not loaded into context as instructions — they run as subprocess calls from within the skill workflow.

## Scripts

| File | Purpose |
|---|---|
| `bugteam_preflight.py` | Skill-path thin entry for shared `_shared/pr-loop/scripts/preflight.py`. Skips pytest when `BUGTEAM_PREFLIGHT_SKIP=1` or no test files exist. |
| `bugteam_fix_hookspath.py` | Skill-path thin entry for shared `_shared/pr-loop/scripts/fix_hookspath.py`. Auto-remediates a stale `core.hooksPath` override. |
| `bugteam_code_rules_gate.py` | Thin skill-path entry; re-exports shared `_shared/pr-loop/scripts/code_rules_gate.py` (of record). |
| `windows_safe_rmtree.py` | Remove a directory tree on Windows by stripping ReadOnly attributes and retrying on failure. |
| `probe_code_rules_enforcer_check.py` | Load `code_rules_enforcer.py` and invoke a named check function against a fixture file. |
| `reflow_skill_md.py` | Reflow the bugteam SKILL.md body to fit line-length limits. |

## Test files

| File | Tests |
|---|---|
| `test_bugteam_preflight.py` | `bugteam_preflight.py` (via thin wrap) |
| `test_bugteam_code_rules_gate.py` | Smoke for thin wrap; behavioral suite is `_shared/pr-loop/scripts/tests/test_code_rules_gate.py` |
| `test_bugteam_fix_hookspath.py` | `bugteam_fix_hookspath.py` (via thin wrap) |
| `test_probe_code_rules_enforcer_check.py` | `probe_code_rules_enforcer_check.py` |
| `test_windows_safe_rmtree.py` | `windows_safe_rmtree.py` |

## Subdirectories

| Directory | Role |
|---|---|
| `bugteam_scripts_constants/` | Named constants imported by the scripts above. |
