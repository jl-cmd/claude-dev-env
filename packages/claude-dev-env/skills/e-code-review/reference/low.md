`low effort → 1 diff pass per target item → no verify → ≥min(files,4) findings`

## Turn 1 — read

Read the unified diff (`git diff @{upstream}...HEAD; git diff HEAD`
to cover both committed and uncommitted changes, or `git diff main...HEAD` /
the target passed as an argument). A target names one or more items, each a PR
number, a branch name, a file path, or `default-range` — the default `git diff`
read named above, which is what this step reads when no target is passed — and
it may mix those forms. A loop round widens a target by adding a path to whatever it
started as, and it names `default-range` as an item whenever the round it
widened was given no target argument, so the original scope stays under review.
When a target names more than one item, read each item's diff and review their
union — a shared hunk counted once, an empty one adding nothing. Skip
test/fixture hunks (`test/`, `spec/`, `__tests__/`, `*_test.*`, `*.test.*`,
`fixtures/`, `testdata/`) — test-file changes are not reviewed at this level.
One read pass per target item, and no more: no subagents, no full-file reads.

## Turn 2 — findings

Flag runtime-correctness bugs visible from the hunk alone: inverted/wrong
condition, off-by-one, null/undefined deref where adjacent lines show the value
can be absent, removed guard, falsy-zero check, missing `await`,
wrong-variable copy-paste, error swallowed in a catch that should propagate.
Also flag — still from the hunk alone — new code that duplicates an existing
helper visible in the diff context, and dead code the diff leaves behind.

Do **not** flag style, naming, perf, missing tests, or anything outside the
hunk.

Target **min(files_changed, 4) findings**, most-severe first, reported in one
call to the structured findings-report call — the mechanism that renders
findings as a typed list in the host UI — with `{level, findings}`; each
entry has `file`, `line`, `summary`, `short_summary` (≤60 characters), and
`failure_scenario`. If you have fewer, do one more pass focused on the largest
changed file and on any **removed** code blocks. Make that call with an empty
findings array only if the diff is trivially correct after that pass. Do not
also print the findings as text.

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
skill's folder) for how to re-run Turn 1 (read) and Turn 2 (findings)
repeatedly — including its exit condition and re-invocation rules. Schedule no
fix pass of your own here: when `--fix` is also present, `reference\loop.md`'s
gate sequence owns the round's fixing and loads `reference\fix.md` for the
mechanics. Do not treat a single pass through this document as complete while
`loop` is active; hand control to that document, and do not stop at Turn 2.

That hand-off applies when this document is entered directly. When a loop round
is already running and has handed this document its target, the round owns the
loop: end at Turn 2 with the findings report and return those findings to
`reference\loop.md`'s gate sequence, rather than handing control to that
document again from here.

When `loop` was not passed, skip this section.