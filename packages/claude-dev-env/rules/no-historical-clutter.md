---
paths: **/*.md
---

# No Historical Clutter in Documentation

**When this applies:** Any Write or Edit to `.md` files.

## Rule

Never reference removed implementations, old defaults, prior behaviors, or how something "used to be" when updating documentation. The current state is all that matters.

## Examples of prohibited patterns

| Pattern | Why it's clutter |
|---------|-----------------|
| "instead of 30" in a pagination rule | The old default no longer exists in code; the rule reader doesn't need to know what it was |
| "previously this used X" | If X is gone, it's noise |
| "before this rule, we did Y" | The rule exists now; the before-state is irrelevant |
| "migrated from Z to W" | If Z is fully removed, the migration story is git history, not documentation |
| "the old implementation did A" | If A is gone, the reader gains nothing from knowing it existed |
| "originally" / "used to be" | Same — dead context |

## What IS allowed

- Comparisons to *currently existing* alternatives (e.g., "use `--paginate --slurp | jq`, not `--jq` alone")
- Rationale that explains *why* a pattern is wrong in terms of present behavior (e.g., "`--jq` runs per-page, so cross-page operations produce wrong results")
- References to external sources for defects that still exist (e.g., gh CLI #10459)

## The test

After writing documentation, ask: **"If someone reads this a year from now, with no knowledge of what came before, does every sentence still make sense and add value?"** If a sentence only adds value to someone who knew the old state, delete it.

## Why

Historical references clog context windows and force readers to mentally filter "what was" from "what is." The git log is the authoritative record of what changed and why. Documentation describes the current contract.
