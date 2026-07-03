---
paths: **/*
---

# No Historical Clutter in Documentation or Comments

**When this applies:** Any Write or Edit to files containing comments or documentation.

**Hook enforcement:** `state-description-blocker` (PreToolUse on Write|Edit) blocks historical/comparative language automatically. See `hooks.json` for registration.

Coverage spans `.md` prose, code comments, and Python module/class/function docstrings; a phrase wrapped in double quotes or backticks inside a docstring counts as a mention and is skipped.

## Rule

Never reference removed implementations, old defaults, prior behaviors, or how something `"used to be"` when updating documentation. The current state is all that matters.

A module or function docstring carries the same describe-current-state-only contract as a `.md` file.

## Examples of prohibited patterns

### In documentation (.md files)

| Pattern | Why it's clutter |
|---------|-----------------|
| `` `"instead of 30"` `` in a pagination rule | The old default `no longer` exists in code; the rule reader doesn't need to know what it was |
| `` `"previously this used X"` `` | If X is gone, it's noise |
| `` `"before this rule, we did Y"` `` | The rule exists now; the before-state is irrelevant |
| `` `"migrated from Z to W"` `` | If Z is fully removed, the migration story is git history, not documentation |
| `` `"the old implementation did A"` `` | If A is gone, the reader gains nothing from knowing it existed |
| `` `"originally"` `` / `` `"used to be"` `` | Same — dead context |

### In code comments

| Pattern | Good replacement |
|---------|-----------------|
| `# Uses X instead of Y` | `# Uses X` |
| `# Previously configured via Z` | `# Configured via Z` |
| `# Now uses the new API client` | `# Uses the new API client` |
| `# No longer supports legacy mode` | `# Supports modern mode only` |
| `// Switched to async processing` | `// Processes asynchronously` |
| `# Replaced by the cache layer` | `# Cache layer handles reads` |

### Hook-detected patterns

The `state-description-blocker` hook (PreToolUse on Write\|Edit) enforces these patterns automatically:

`instead of`, `previously`, `now uses/does/handles/supports/names/includes`, `was previously`, `were previously`, `was formerly`, `was added`, `used to`, `no longer`, `has/have been updated/changed`, `replaced by`, `replaces`, `superseded by`, `supersedes`, `changed from`, `changes from`, `switched from/to`, `migrated from/to`, `moved to/into`, `extracted as`, `updated to`, `originally`, `as of`

## What IS allowed

- Comparisons to *currently existing* alternatives (e.g., "use `--paginate --slurp | jq`, not `--jq` alone")
- Rationale that explains *why* a pattern is wrong in terms of present behavior (e.g., "`--jq` runs per-page, so cross-page operations produce wrong results")
- References to external sources for defects that still exist (e.g., gh CLI #10459)

## The test

After writing documentation, ask: **"If someone reads this a year from now, with no knowledge of what came before, does every sentence still make sense and add value?"** If a sentence only adds value to someone who knew the old state, delete it.

## Why

Historical references clog context windows and force readers to mentally filter "what was" from "what is." The git log is the authoritative record of what changed and why. Documentation describes the current contract.
