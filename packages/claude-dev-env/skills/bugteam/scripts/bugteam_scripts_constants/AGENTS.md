# bugteam/scripts/bugteam_scripts_constants

Python package of named constants imported by the bugteam scripts. Each module holds the constants for one script; importing from this package keeps magic values out of the script bodies.

## Modules

| File | Constants for |
|---|---|
| `probe_code_rules_enforcer_check_constants.py` | `probe_code_rules_enforcer_check.py` — enforcer module path and function name constants. |
| `reflow_skill_md_constants.py` | `reflow_skill_md.py` — line-length and formatting constants. |
| `windows_safe_rmtree_constants.py` | `windows_safe_rmtree.py` — retry count and wait constants. |
| `__init__.py` | Empty package marker. |

Preflight, fix_hookspath, and code_rules_gate constants live under package shared `pr_loop_shared_constants` with the shared implementations.

## Convention

Scripts import from this package at module scope. No constant is defined inline in a script body — the hook enforces this at write time.
