# skills_pr_loop_constants

Python package of named constants for the `pr-loop` shared scripts. All constants are `UPPER_SNAKE_CASE` module-level names imported by the sibling scripts.

## Key files

| File | Role |
|---|---|
| `__init__.py` | Package marker. |
| `path_resolver_constants.py` | Path template strings and format constants: workspace directory naming, worktree directory name, diff patch filename pattern, outcome XML filename patterns, fix status values, audit constraint texts, audit category entries, fix execution steps, and fix constraint texts. |
| `preflight_constants.py` | Constants used by `preflight_worktree.py` for exit codes and output marker strings. |
| `handoff_constants.py` | Filename, path-segment, and template constants for the durable handoff writer. |
| `pacer_constants.py` | Entry-skill names, pacer tokens, CLI flags, and result keys for `select_converge_pacer.py`. |
| `portable_driver_constants.py` | Phase names, next-action tokens, wait delays, blockers, CLI flags, and result keys for `portable_converge_driver.py`. |
| `converge_task_list_constants.py` | Task ids, kinds, and CLI flags for `build_converge_task_list.py`. |

## Usage

Scripts import directly from the package:

```python
from skills_pr_loop_constants.path_resolver_constants import PER_PR_WORKSPACE_TEMPLATE
```
