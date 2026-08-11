# pr_converge_skill_constants

Importable Python constants module for the `pr-converge` skill. Script-specific constants (CLI args, markdown patterns, reflow settings) live in `scripts/pr_converge_scripts_constants/` and import from here.

## Key files

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `constants.py` | All runtime and API constants: bot logins, review states, GH API path templates, bugbot/bugteam detection patterns, exit codes |

## Exported constants (selected)

| Constant | Purpose |
|---|---|
| `CURSOR_BOT_LOGIN` | Login string for the Cursor bugbot reviewer |
| `COPILOT_REVIEWER_LOGIN` | Login string for the Copilot reviewer bot |
| `ALL_COPILOT_CLEAN_REVIEW_STATES` | Tuple of review states that count as clean for Copilot |
| `BUGBOT_DIRTY_BODY_REGEX` | Regex that matches a bugbot review body reporting findings |
| `GH_REVIEWS_PATH_TEMPLATE` | `gh api` path template for PR reviews |
| `GH_INLINE_COMMENTS_PATH_TEMPLATE` | `gh api` path template for PR inline comments |

## Conventions

- All path templates use `str.format(**kwargs)` with keys `owner`, `repo`, `number`.
- `packages/claude-dev-env/skills/pr-converge/scripts/pr_converge_scripts_constants/pr_converge_constants.py` re-exports everything here via `from pr_converge_skill_constants.constants import ...` so scripts can import from either location.
