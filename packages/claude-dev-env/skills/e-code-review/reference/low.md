# low effort — full review procedure

## Framing

`low effort → 1 diff pass → no verify → every finding returned`

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

Return every finding, most-severe first (bugs before nits), one line each,
tagging each with its severity: `path/to/file.ext:123 — [bug|nit] what's wrong
and the concrete failure`. Do not call the ReportFindings tool even if it is
available — these plain lines are the output. If you have no findings, do one
more pass focused on the largest changed file and on any **removed** code
blocks. Output `(none)` only if the diff is trivially correct after that pass.
This procedure runs single-pass with no subagents — say so if asked what
executed.

## Loop

When the hub invocation includes `loop`, return this findings set to the hub and
follow `SKILL.md` Optional loop mode. Each re-review re-runs **this low
procedure**. Low tags `[bug|nit]` when the hunk supports that label; any
untagged non-empty finding counts as a `bug` under loop. `(none)` is clean.
Without `loop`, return the findings and stop.
