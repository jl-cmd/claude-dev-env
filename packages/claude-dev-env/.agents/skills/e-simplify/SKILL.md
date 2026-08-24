---
name: e-simplify
description: >-
  Cleanup-only pass on the current diff — reuse, simplification, efficiency,
  altitude — that fixes what it finds directly; no correctness-bug hunting.
  Triggers: /e-simplify.
---

# e-simplify

**Core principle:** Four parallel cleanup angles (reuse, simplification, efficiency, altitude) over the current diff, applied directly — not a bug hunt, and not a report.

## Gotchas

- This skill fixes code quality, not correctness. A request for bug-hunting belongs to `/e-code-review`, not here — see the refusal case below.
- Applying a fix that changes intended behavior, or that reaches well outside the reviewed diff, is worse than leaving a flagged item unfixed — skip and note it instead of stretching the fix to cover it.

## When this skill applies

Triggers: `/e-simplify` on the current diff (or a PR/branch/path passed as an argument).

**Refusal cases — first match wins:**

- **Asked to find correctness bugs (crashes, wrong output, security issues) rather than cleanup.** Respond exactly: `That's a correctness review — use /e-code-review, not this skill.`

## The process

`/simplify → 4 cleanup agents in parallel → apply the fixes`

You are improving the quality of the changed code, not hunting for bugs. Review
it for reuse, simplification, efficiency, and altitude issues, then fix what you
find. Do not look for correctness bugs — that is what `/code-review` is for.

### Phase 0 — Gather the diff

Run `git diff @{upstream}...HEAD` (or `git diff main...HEAD` / `git diff HEAD~1`
if there's no upstream) to get the unified diff under review. If there are
uncommitted changes, or the range diff is empty, also run `git diff HEAD` and
include the working-tree changes in scope — the review often runs before the
commit. If a PR number, branch name, or file path was passed as an argument,
review that target instead. Treat this diff as the review scope.

### Phase 1 — Review (4 cleanup agents in parallel)

Launch **4 independent review agents** via the Agent tool, all in a
single message so they run concurrently. Pass each agent the diff and one of
the four angles below. Each returns its findings with `file`, `line`, a
one-line `summary`, and the concrete cost (what is duplicated, wasted, or
harder to maintain).

#### Reuse

Flag new code that re-implements something the codebase
already has — Grep shared/utility modules and files adjacent to the change,
and name the existing helper to call instead.

#### Simplification

Flag unnecessary complexity the diff adds: redundant or derivable state,
copy-paste with slight variation, deep nesting, dead code left behind. Name
the simpler form that does the same job.

#### Efficiency

Flag wasted work the diff introduces: redundant computation or repeated I/O,
independent operations run sequentially, blocking work added to startup or
hot paths. Also flag long-lived objects built from closures or captured
environments — they keep the entire enclosing scope alive for the object's
lifetime (a memory leak when that scope holds large values); prefer a
class/struct that copies only the fields it needs. Name the cheaper
alternative.

#### Altitude

Check that each change is implemented at the right depth, not as a fragile
bandaid. Special cases layered on shared infrastructure are a sign the fix
isn't deep enough — prefer generalizing the underlying mechanism over adding
special cases.

### Phase 2 — Apply the fixes

Wait for all four agents to complete, dedup findings that point at the same
line or mechanism, and fix each remaining one directly. Skip any finding whose
fix would change intended behavior, require changes well outside the reviewed
diff, or that you judge to be a false positive — note the skip rather than
arguing with it. Finish with a brief summary of what was fixed and what was
skipped (or confirm the code was already clean).

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This hub — the full cleanup procedure, refusal case |

## Folder map

- `SKILL.md` — hub: full procedure, refusal case.
