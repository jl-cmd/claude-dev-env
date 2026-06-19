# skills_pr_loop_constants

Python package of named constants for the `pr-loop` shared scripts. All constants are `UPPER_SNAKE_CASE` module-level names imported by the sibling scripts.

## Key files

| File | Role |
|---|---|
| `__init__.py` | Package marker. |
| `path_resolver_constants.py` | Path template strings and format constants: workspace directory naming, worktree directory name, diff patch filename pattern, outcome XML filename patterns, loop state filename, fix status values, audit constraint texts, audit category entries, fix execution steps, fix constraint texts, and XML serialization settings. |
| `preflight_constants.py` | Constants used by `preflight_worktree.py` for exit codes and output marker strings. |

## Usage

Scripts import directly from the package:

```python
from skills_pr_loop_constants.path_resolver_constants import LOOP_STATE_FILENAME
```
