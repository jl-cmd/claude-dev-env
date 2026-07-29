`medium effort → 3+5 angles → 1-vote verify`

You are reviewing for **precision** at medium effort: every finding you surface
should be one a maintainer would act on.

## Phase 0 — Gather the diff

Run `git diff @{upstream}...HEAD` (or `git diff main...HEAD` / `git diff HEAD~1`
if there's no upstream) to get the unified diff under review. If there are
uncommitted changes, or the range diff is empty, also run `git diff HEAD` and
include the working-tree changes in scope — the review often runs before the
commit. If a target was passed as an argument, review that target instead. A
target names one or more items, each a PR number, a branch name, a file path, or
`default-range` — the diff this phase gathers when no target is passed — and it
may mix those forms. A loop round widens a target by adding a path to whatever
it started as, and it names `default-range` as an item whenever the round it
widened was given no target argument, so the original scope stays under review.
When a target names more than one item, gather each item's diff and take their
union — a shared hunk counted once, an empty one adding nothing — as the
target's diff. Treat this diff as the review scope.

## Phase 1 — Find candidates (3 correctness angles + 3 cleanup angles + 1 altitude angle + 1 conventions angle)

Run **8 independent finder angles** via the Agent tool. Each surfaces
candidate findings with `file`, `line`, a one-line `summary`, and a concrete
`failure_scenario`. If the Agent tool is not available in your current tool
set, do not error — perform each angle (and each verification) yourself,
sequentially, in this context.

### Angle A — line-by-line diff scan

Read every hunk in the diff, line by line. Then Read the enclosing function for
each hunk — bugs in unchanged lines of a touched function are in scope (the PR
re-exposes or fails to fix them). For every line ask: what input, state, timing,
or platform makes this line wrong? Look for inverted/wrong conditions,
off-by-one, null/undefined deref, missing `await`, falsy-zero checks,
wrong-variable copy-paste, error swallowed in catch, unescaped regex metachars.

### Angle B — removed-behavior auditor

For every line the diff DELETES or replaces, name the invariant or behavior it
enforced, then search the new code for where that invariant is re-established.
If you can't find it, that's a candidate: a removed guard, a dropped error
path, a narrowed validation, a deleted test that was covering a real case.

### Angle C — cross-file tracer

For each function the diff changes, find its callers (Grep for the symbol) and
check whether the change breaks any call site: a new precondition, a changed
return shape, a new exception, a timing/ordering dependency. Also check callees:
does a parallel change in the same PR make a call unsafe?

### Reuse

The angles above hunt for bugs; this one and the next two hunt for cleanup in
the changed code. Flag new code that re-implements something the codebase
already has — Grep shared/utility modules and files adjacent to the change,
and name the existing helper to call instead.

### Simplification

Flag unnecessary complexity the diff adds: redundant or derivable state,
copy-paste with slight variation, deep nesting, dead code left behind. Name
the simpler form that does the same job.

### Efficiency

Flag wasted work the diff introduces: redundant computation or repeated I/O,
independent operations run sequentially, blocking work added to startup or
hot paths. Also flag long-lived objects built from closures or captured
environments — they keep the entire enclosing scope alive for the object's
lifetime (a memory leak when that scope holds large values); prefer a
class/struct that copies only the fields it needs. Name the cheaper
alternative.

### Altitude

Check that each change is implemented at the right depth, not as a fragile
bandaid. Special cases layered on shared infrastructure are a sign the fix
isn't deep enough — prefer generalizing the underlying mechanism over adding
special cases.

### Conventions (CLAUDE.md)

Find the CLAUDE.md files that govern the changed code: the user-level
~/.claude/CLAUDE.md, the repo-root CLAUDE.md, plus any CLAUDE.md or
CLAUDE.local.md in a directory that is an ancestor of a changed file (a
directory's CLAUDE.md only applies to files at or below it). Read each one
that exists, then check the diff for clear violations of the rules they state.

Only flag a violation when you can quote the exact rule and the exact line
that breaks it — no style preferences, no vague "spirit of the doc"
inferences. In the finding, name the CLAUDE.md path and quote the rule so the
report can cite it. If no CLAUDE.md applies, return nothing for this angle.

Cleanup, altitude, and conventions candidates use the same
`file`/`line`/`summary` shape; in `failure_scenario`, state the concrete
cost (what is duplicated, wasted, harder to maintain, or which CLAUDE.md rule
is broken) instead of a crash. Correctness bugs always outrank cleanup,
altitude, and conventions findings.

Pass every candidate with a nameable failure scenario through — finders that
silently drop half-believed candidates bypass the verify step and are the
dominant cause of misses.

## Phase 2 — Verify (1-vote, 3-state)

Dedup candidates that point at the same line/mechanism, keeping the one with
the most concrete failure scenario. For each remaining candidate, run **one
verifier** via the Agent tool: give it the diff, the relevant
file(s), and the candidate, and have it return exactly one of:

- **CONFIRMED** — can name the inputs/state that trigger it and the wrong
  output or crash. Quote the line.
- **PLAUSIBLE** — mechanism is real, trigger is uncertain (timing, env,
  config). State what would confirm it.
- **REFUTED** — factually wrong (code doesn't say that) or guarded elsewhere.
  Quote the line that proves it.

Keep candidates where the vote is CONFIRMED or PLAUSIBLE.

## Output

Report this review's results — `{level, findings}` — through the structured
findings-report call: the mechanism that renders a review's results as a typed
list in the host UI, ranked most-severe first. Each entry has `file`, `line`,
`summary`, `short_summary` — the claim compressed to ≤60 characters, no
rationale or consequence clause — `failure_scenario`, and `category` — a short
kebab-case slug for the angle that produced it (`correctness`,
`simplification`, `efficiency`, `reuse`, `altitude`, `conventions`, or a more
specific slug like `test-coverage` when one fits better) — plus `verdict` when
a verify pass produced one. If nothing survives verification, make that call
with an empty array. Do not also print the findings as text, and do not create
or publish an artifact of the review — the structured call is the report.

## Applying fixes (--fix)

The `--fix` flag was passed. Follow `reference\fix.md` (relative
to this skill's folder) for the exact fix, code-rules-gate, and skip-handling
behavior — it governs which agent applies each fix, how the code-rules gate
runs, how a skip is logged, and how outcomes get reported. Do not repeat the
findings as text; follow that document's reporting rules once fixes land.

When `loop` is also set, skip this section.

## If findings are fixed later

Whenever a reported finding is fixed later in this session — the user asks you
to fix it, or later work fixes it incidentally — follow `reference\fix.md`'s
reporting rules again: report the same findings through the structured
findings-report call, each carrying an `outcome`. Do not repeat the findings
as text. Make that call immediately after the fixes land, before any prose
summary; the host UI's per-finding status updates only from that call.

## Looping (`loop`)

The `loop` arg was passed. Follow `reference\loop.md` (relative to this
skill's folder) for how to re-run Phases 0–2 and Output repeatedly — including
its exit condition and re-invocation rules. Schedule no fix pass of your own
here: when `--fix` is also present, `reference\loop.md`'s gate sequence owns the
round's fixing and loads `reference\fix.md` for the mechanics. Do not treat a
single pass through this document as complete while `loop` is active; hand
control to that document, and do not stop at Output.

That hand-off applies when this document is entered directly. When a loop round
is already running and has handed this document its target, the round owns the
loop: end at Output with the findings report and return those findings to
`reference\loop.md`'s gate sequence, rather than handing control to that
document again from here.

When `loop` was not passed, skip this section.