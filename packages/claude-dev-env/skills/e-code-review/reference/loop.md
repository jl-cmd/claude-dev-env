# Loop until clean

## Act

`loop` on the hub command authorizes the full cycle. After the effort level procedure returns findings, run the gate sequence below immediately.

Do not ask whether to fix, which nits to keep, whether to commit or push, or whether to re-review. Do not open a plan fork. Do not end the turn on a recommendation.

Report progress while you work. Stop for the user only on a terminal outcome below.

## Where fixes come from

When `--fix` is also set, each round's fix pass runs `reference\fix.md`
(relative to this skill's folder) — it owns which agent applies each fix, the
commit gate, skip logging, and outcome reporting. Apply the gate sequence below
on top of it: it decides whether a round fixes, commits, pushes, and
re-reviews.

## Scope stays narrow

Auto-fix only verified findings on the review target. Leave deferred PR-body follow-ups and unrelated refactors alone.

## How to class each finding

Use the finding's verified `severity` when the level emits one.

A finding is a `nit` only when that severity is `nit`. Runtime-correctness, security, data-loss, compatibility, and every other non-nit finding is a `bug`.

If the level emits no severity (for example untagged `low` lines), consult your advisor to determine classification.

## Required checks

"Run required checks" means: run `~/.claude/_shared/pr-loop/scripts/code_rules_gate.py --repo-root <repo root> <changed/added files>` against every file changed or added in the round. On any violation, fix it and re-run the exact same command again — repeat until it reports clean.

## Each round reviews new code

A repair diff is new code. From the second round on, the round runs the level
file end to end at the new head. The round's scope is the level's own review
target — the diff or path the level gathers up front, called Phase 0 in
`medium.md` and `xhigh.md` — taken against that target's base. A repair edit
landing outside that target widens the next round's scope to cover it.

## Dangerous diffs take two full rounds

A diff is dangerous when it touches deletion paths, locks or other concurrency
control, or shared mutable state. A deletion path is a runtime path that removes
data or files; a dead-code cleanup is not one. Each round names whether the diff
it reviewed is dangerous. A dangerous diff holds the loop open until two full
rounds have reviewed it. A repair that rewrites the dangerous surface restarts
the two-round count at the first round that reviews the rewritten surface.

The round's progress report is where both facts are recorded: the dangerous
classification, and the dangerous-round count written as `N of M`.

## A shape change names its readers

When a repair changes a key, an identifier format, or a data shape, list every
reader of the shape it changed and state how each one reads the new shape. The
list goes in the round's progress report.

The round that follows a posted list checks each reader on that list against the
new shape and names each reader with its result in that round's progress report.
The obligation discharges when every reader on the list has been named with a
result — not when a reader is fixed, and not when a round merely happens.

A broken reader outside the review target does not block the loop and does not
widen scope. Check it, record its result, and hand it off as a reported finding:
name it in the round report, and carry it into the ready-for-review message and
the pull request body.

A round may not mark ready while a broken off-target reader exists unless the
ready message names it.

## Terminal outcomes

Every round ends by running the three gates below, in order: gate 1, then gate
2, then gate 3.

**Gate 1 — obligations.** Gate 1 is evaluated first in the sequence, and its
answer turns on the round's open obligations alone — the findings are in hand by
now, and no content they carry changes it. Ask only: does any obligation remain
open? Two kinds exist.

- A dangerous diff that has had fewer than two full rounds.
- A posted shape-change list that no round has discharged.

Gate 1 states its answer and stops there: an obligation remains open, or none
does. It states no re-entry, no continuation, and no routing. Gate 3 is the sole
router — every path out of a round passes through it.

**Gate 2 — findings.** Take the one case that matches the round's findings.

- Any bug-severity finding: validate each one with an advisor before touching
  code — confirm it's real and confirm the intended fix — then fix all
  validated findings, bugs and nits, on the review target.
- Nits only, with at least one nit present: fix all of them on the review
  target.
- No findings at all: make no edits.

Gate 2 then ends by stating one of exactly two outcomes: unresolved findings
remain, or none remain. A refuted bug is resolved. A fixed nit is resolved. A
fixed validated bug is resolved. A handed-off off-target finding is resolved once
its hand-off is complete — checked, its result recorded, and named in the round
report — whether or not the problem behind it is solved. Gate 3 reads that stated
outcome, never a case label.

**Gate 3 — exit test.** Terminate only when all three of these hold:

- gate 1 shows no open obligation;
- gate 2 states no unresolved findings remain;
- this round produced no edits.

Any other combination runs the round tail and re-enters the loop. On termination,
post the proof-of-work PR comment when the target is a PR, then run `gh pr ready`
for a draft PR, or state ready otherwise.

Gate 3 points at gate 1 for the obligation answer. It does not restate the
two-round rule or the shape-reader rule; each of those keeps its one home in its
own section above.

**The round tail.** Run required checks. When this round produced edits, confirm
those edits are committed and pushed; make the commit yourself, once, only when
no `--fix` path has already made one. Then start the next round under *Each round
reviews new code*.

Do not drop findings to force ready. Without `loop`, run one review at the selected level, fix, and return every validated finding.
