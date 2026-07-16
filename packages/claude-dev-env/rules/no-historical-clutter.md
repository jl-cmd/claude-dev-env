---
paths:
  - "**/*.md"
  - "**/*.py"
  - "**/*.mjs"
  - "**/*.js"
  - "**/*.ts"
  - "**/*.ps1"
  - "**/*.sh"
---

# No Historical Clutter in Documentation or Comments

Never reference removed implementations, old defaults, prior behaviors, or earlier contracts when updating documentation or comments. The current state is all that matters. A module or function docstring carries the same describe-current-state-only contract as a `.md` file.

`state_description_blocker` (PreToolUse on Write|Edit) blocks historical and comparative phrases in `.md` prose, code comments, and Python docstrings; a phrase wrapped in double quotes or backticks inside a docstring counts as a mention and is skipped. The denial names the matched phrases and shows a rewrite example.

## What stays allowed

- Comparisons to alternatives that still exist (for example, "use `--paginate --slurp | jq`, not `--jq` alone")
- Rationale that explains why a pattern is wrong in terms of present behavior (for example, "`--jq` runs per-page, so cross-page operations produce wrong results")
- References to external sources for defects that still exist (for example, gh CLI #10459)

## The test

After writing, ask: if someone reads this a year from now with no knowledge of earlier states, does every sentence still make sense and add value? If a sentence only helps someone who knew an earlier state, delete it.
