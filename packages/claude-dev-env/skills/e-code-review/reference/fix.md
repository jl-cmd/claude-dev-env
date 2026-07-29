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

Before returning, the resumed agent runs the code-rules gate over its own
change:

1. Run `~/.claude/_shared/pr-loop/scripts/code_rules_gate.py --repo-root <repo
   root> <changed/added files>` against every file it changed or added.
2. If the gate reports violations, fix them and re-run the exact same command.
3. Repeat until the gate returns clean.
4. Only after a clean gate result does the agent return control and report
   its outcome.

This gate commits nothing. The fix lands in the working tree and stays
uncommitted; committing belongs to whatever invoked this document.

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