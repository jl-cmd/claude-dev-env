---
name: e-simplify
description: >-
  Cleanup-only pass on the current diff — reuse, simplification, efficiency,
  altitude — that fixes what it finds directly; no correctness-bug hunting.
  Triggers: /e-simplify.
---

# e-simplify

**Core principle:** Four cleanup angles (reuse, simplification, efficiency, altitude) inspect the current diff and apply safe fixes directly — not a bug hunt and not a report.

The mandatory first executable action is:

`python ../review-router/scripts/review_router_cli.py resolve --review-kind e-simplify --cwd <cwd> --arguments "$ARGUMENTS"`

Call `arm` for every returned slot in order, dispatch each exact Agent|Task payload, and call `close` after the route completes. The registered Agent|Task hook enforces every spawn.

## Gotchas

- This skill fixes code quality, not correctness. A request for bug-hunting belongs to `/e-code-review`, not here. Respond exactly: `That's a correctness review — use /e-code-review, not this skill.`
- Applying a fix that changes intended behavior, or reaches well outside the reviewed diff, is worse than leaving a flagged item unfixed. Skip and note it instead.

## When this skill applies

Triggers: `/e-simplify` on the current diff or a PR, branch, or path passed as an argument.

Refuse correctness bugs, crashes, wrong output, and security issues with the exact refusal above.

## The process

Gather the diff with `git diff @{upstream}...HEAD`, or `git diff main...HEAD` / `git diff HEAD~1` when no upstream exists. If uncommitted changes exist or the range is empty, include `git diff HEAD`. If an argument names a PR, branch, or path, review that target. Treat the complete gathered surface as scope.

Review four independent cleanup angles: reuse, simplification, efficiency, and altitude. Each finding carries `file`, `line`, a one-line `summary`, and the concrete cost. Apply safe fixes directly. Skip findings whose fix changes intended behavior, reaches outside scope, or belongs to correctness review. Finish with a brief summary of fixes and skips.

### Reuse

Find new code that re-implements existing helpers or adjacent patterns. Name the existing helper to call.

### Simplification

Find redundant or derivable state, copy-paste with slight variation, deep nesting, and dead code. Name the simpler equivalent.

### Efficiency

Find redundant computation or repeated I/O, independent operations run sequentially, blocking work on startup or hot paths, and long-lived objects that capture large environments. Name the cheaper alternative.

### Altitude

Check that each change lives at the owning abstraction. Generalize shared infrastructure when a special case makes the fix fragile.

## Child execution contract

Every derived prompt embeds the complete cleanup behavior because child agents receive no parent skill context. Each prompt includes the current diff scope, all four angles, direct-fix behavior, finding shape, refusal, and skip rules.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Cleanup workflow and guarded runtime adapter |
| `../review-router/scripts/review_router_cli.py` | Resolve, arm, and close operations |

## Folder map

- `SKILL.md` — cleanup workflow and runtime adapter.
