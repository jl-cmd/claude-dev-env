# bugteam/scripts/bugteam_scripts_constants

Python package of named constants imported by the bugteam scripts. Each module holds the constants for one script; importing from this package keeps magic values out of the script bodies.

## Modules

| File | Constants for |
|---|---|
| `bugteam_preflight_constants.py` | `bugteam_preflight.py` — env var name, hooks path suffix, exit codes, ignore dirs, argument tuples, config filenames. |
| `bugteam_code_rules_gate_constants.py` | `bugteam_code_rules_gate.py` — gate-related path and exit-code constants. |
| `bugteam_fix_hookspath_constants.py` | `bugteam_fix_hookspath.py` — canonical hooks path, remediation message strings. |
| `claude_permissions_common_constants.py` | `_bugteam_permissions_common.py` — settings JSON keys, glob patterns for the grant/revoke scripts. |
| `probe_code_rules_enforcer_check_constants.py` | `probe_code_rules_enforcer_check.py` — enforcer module path and function name constants. |
| `reflow_skill_md_constants.py` | `reflow_skill_md.py` — line-length and formatting constants. |
| `windows_safe_rmtree_constants.py` | `windows_safe_rmtree.py` — retry count and wait constants. |
| `__init__.py` | Empty package marker. |

## Convention

Scripts import from this package at module scope. No constant is defined inline in a script body — the hook enforces this at write time.
