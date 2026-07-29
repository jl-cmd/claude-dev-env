# Fix Behavior (--fix)

When `--fix` is passed, apply the reviewed findings to the working tree.

## Resume the finding agent

For each finding, resume the same Agent-tool agent instance that originally
surfaced it. That agent applies all relevant fixes, which you provide guidance
on in your resume prompt.

At `low` — and any time the Agent tool is unavailable — no finder agent exists
to resume. Apply the fixes yourself, sequentially, in this context, holding to
every rule below.

## Code-rules gate

Before returning, the resumed agent runs the code-rules gate with the same bare
call every other surface in this skill uses:

1. Run `~/.claude/_shared/pr-loop/scripts/code_rules_gate.py --repo-root <repo
   root>` with no file paths and no `--only-under` prefix.
2. If the gate reports violations **on lines this fix already owns** (the files
   and added lines the fix changed), fix them and re-run the exact same command.
3. A violation on a path or added line outside this fix's own work is reported
   or skipped — it is not force-fixed into unrelated files. Log each skip with
   the path and reason, then continue.
4. Repeat until every violation on this fix's own work is clean (or skipped with
   a logged reason for out-of-scope hits).
5. Only after that result does the agent return control and report its outcome.

A file path named on the command line puts the gate in whole-file scope and can
churn on untouched lines; keep the call bare.

This gate commits nothing. The fix lands in the working tree and stays
uncommitted; committing belongs to whatever invoked this document. The bare
code-rules call covers the merge-base surface and staged added lines only —
working-tree-only lines enter that scope after stage or commit.

Under a bare `--fix` — this document invoked without `loop` — nothing
downstream commits either, and that is the intended outcome: a one-shot fix
pass leaves its fixes uncommitted in the working tree for the user to review
and commit (stage first if you re-run the gate on those lines). Under `loop`,
the round tail in `reference\loop.md` stages, runs required checks, and
commits the round's fixes.

## Skip candidates

Skip a finding when fixing it would change intended behavior, require changes
well outside the reviewed diff, or the finding itself is judged a false
positive.

Every logged skip surfaces exactly once, batched together, in a single 
consolidated list presented to the user at the very end of the fix pass 
— after every other finding has been fixed, marked not-needed, or skipped, 
and never before.

## Reporting outcomes

After fixes land, report the same findings list again through the structured
findings-report call — the mechanism that renders this review's results as a
typed list in the host UI — with each finding now carrying an `outcome`:
`fixed`, `no_change_needed` (the finding was wrong or already handled), or
`skipped` (real but not applied). Do not repeat the findings as text in the
response body; the structured call is the record the host UI reads, and the
batched skip list from above goes in the prose that follows it.

## If findings are fixed later

Whenever a reported finding is fixed later in the session — the user asks for
the fix, or later work fixes it incidentally — call the structured
findings-report call again with the same findings, each carrying an
`outcome` (`fixed`, `no_change_needed`, or `skipped`). Do not repeat the
findings as text. Make that call immediately after the fixes land, before any
prose summary.