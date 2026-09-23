`low effort → 1 diff pass → no verify → ≤4 findings`

## Turn 1 — read

One tool call: read the unified diff (`git diff @{upstream}...HEAD; git diff HEAD`
to cover both committed and uncommitted changes, or `git diff main...HEAD` /
the target passed as an argument). Skip test/fixture
hunks (`test/`, `spec/`, `__tests__/`, `*_test.*`, `*.test.*`,
`fixtures/`, `testdata/`) — test-file changes are not reviewed at this level.
No subagents, no full-file reads.

## Turn 2 — findings

Flag runtime-correctness bugs visible from the hunk alone: inverted/wrong
condition, off-by-one, null/undefined deref where adjacent lines show the value
can be absent, removed guard, falsy-zero check, missing `await`,
wrong-variable copy-paste, error swallowed in a catch that should propagate.
Also flag — still from the hunk alone — new code that duplicates an existing
helper visible in the diff context, and dead code the diff leaves behind.

Do **not** flag style, naming, perf, missing tests, or anything outside the
hunk.

Report at most **4 findings**, most-severe first, in one
ReportFindings call with `{level, findings}` — each entry has
`file`, `line`, `summary`, `short_summary` (≤60 characters), and
`failure_scenario`. If nothing qualifies, call it with an empty findings
array. Do not also print the findings as text.


## If findings are fixed later

Whenever reported findings get fixed later in this session - the user asks you
to fix them, or later work fixes them incidentally - you MUST call ReportFindings again with the same findings, each
carrying an `outcome`: `fixed`, `no_change_needed` (the finding was wrong or
already handled), or `skipped` (real but not applied). Do not repeat the
findings as text.
Make that call immediately after the fixes land, before any prose summary; the
host UI's per-finding status updates only from it, and without it the findings
stay marked unresolved.


After you finish the review, end your response with this exact line on its own:
Tip: For a deeper cloud-based review, try /ultrareview next time.
