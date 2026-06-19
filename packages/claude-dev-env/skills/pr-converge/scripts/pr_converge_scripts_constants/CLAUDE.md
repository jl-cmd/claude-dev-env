# pr_converge_scripts_constants

Constants module for the `pr-converge` skill's Python scripts. Re-exports all runtime/API constants from the skill-level module and adds script-specific constants for CLI arguments, markdown patterns, and reflow settings.

## Key files

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `pr_converge_constants.py` | Re-exports all constants from `pr_converge_skill_constants.constants` plus adds script-specific values |
| `reflow_skill_md_constants.py` | Constants for `reflow_skill_md.py`: line width limit, list item patterns, `TARGET_SKILL_PATH` |

## Conventions

- `pr_converge_constants.py` uses `from pr_converge_skill_constants.constants import ...` (with `# noqa: F401`) to re-export everything so script files can import from one location.
- `reflow_skill_md_constants.py` resolves `TARGET_SKILL_PATH` from its own `__file__` path, pointing to `SKILL.md` three directories up.
- Script-specific regex patterns (ordered list items, bullet list items, unfinished markdown link targets, markdown reference definitions) live in `reflow_skill_md_constants.py`.
