# Loop until clean

## Act

`loop` on the hub command authorizes the full cycle. After the effort level procedure returns findings, run the gate sequence below immediately.

Do not ask whether to fix, which nits to keep, whether to commit or push, or whether to re-review. Do not open a plan fork. Do not end the turn on a recommendation.

Report progress while you work. Stop for the user only on a terminal outcome below.

## Where fixes come from

A round fixes whether or not `--fix` is set. Gate 2 below applies the round's
fixes on every run, and its three cases read the same way with the flag and
without it. What `--fix` adds is `fix.md`'s mechanics, not permission to fix:
the flag decides where the mechanics come from, never whether a round fixes at
all.

When `--fix` is also set, the round's fixing happens inside the gate sequence
below. Gate 2 is the only place a round applies a fix, and there is no separate
fix pass sitting around the round. Gate 2 loads `reference\fix.md` (relative to
this skill's folder) for the mechanics — which agent applies each fix, agent
resume, the code-rules gate, skip logging, and outcome reporting — while the
gate sequence decides whether a round fixes, commits, pushes, and re-reviews.

## Scope stays narrow

Auto-fix only verified findings on the review target. Leave deferred PR-body follow-ups and unrelated refactors alone.

## How to class each finding

Every retained finding carries a verified `severity` and a verification
`verdict` (`CONFIRMED` or `PLAUSIBLE`). The frozen severity set is exactly
`blocker`, `high`, `medium`, `low`, `nit`.

A finding is a `nit` only when that severity is `nit`. Runtime-correctness,
security, data-loss, compatibility, and every other non-nit finding is a
`bug`.

A finding that lacks severity is **unclassified**. Consult the assigned
advisor to classify it before Gate 2. When that advisor is unreachable,
terminate with `advisor_blocked` and preserve draft state.

A finding this document has already classed keeps that class at every level. An
on-target shape-reader break is `bug` under *A shape change names its readers*;
no advisor call reopens that.

## Required checks

"Run required checks" means: run
`~/.claude/_shared/pr-loop/scripts/code_rules_gate.py --repo-root <repo root>`
with no file paths and no `--only-under` prefix. On a violation on lines this
round already owns, fix it and re-run the exact same command until clean. A
violation outside the review target is reported or skipped — not force-fixed into
unrelated files — and the skip is logged with path and reason.

That bare call gates the git diff since the merge-base (and any staged added
lines the gate already includes). Working-tree lines that are neither staged
nor committed sit outside that scope until they are staged or committed. Gate 2
leaves its edits uncommitted, so the round tail stages those edits before
required checks when this round produced edits.

Two failure scenarios keep the call bare. A file path named on the command line
puts the gate in whole-file scope on that file: a CODE_RULES violation on a line
this round never touched fails the round and churns the loop. An `--only-under`
prefix that matches nothing in the diff leaves the gate zero files to inspect and
exits clean, so a run that inspected nothing reads as a pass.

## Each round reviews new code

A repair diff is new code. From the second round on, the round runs the level
file end to end at the new head. End to end means that file's review phases, up
to and including its findings report; the round stops there and brings those
findings back to the gate sequence below. It does not run the level file's
*Looping* section — that section hands control to this document, and the round
is already inside it. The round's scope is the level's own review
target — the diff or path the level gathers up front, called Phase 0 in
`medium.md` and `xhigh.md` — taken against that target's base. A repair edit
landing outside that target widens the next round's scope to cover it: the next
round's review target is the original target **plus** that path, and the round
reviews both. A later widening adds to that target the same way.

The widened target is what the round hands the level file. When a round runs the
level file end to end, it passes the current review target — the original target
plus every path a widening has since added — as that run's target argument, in
place of the argument the first round was given. When the first round was given
no target argument, the original target is the item `default-range` — the level
file's own default gather — so the widened target is `default-range` plus every
added path, and the range the first round reviewed stays in scope. The level
file gathers what the round hands it, so a widened path is gathered and reviewed
like any other part of the target.

## Reviewed heads and the three-head cap

Record every distinct git head the loop reviews. Reviewing a **new** head
increments the reviewed-head count by one. Re-reviewing the **same** head does
not increment the count.

The cap is **three** distinct reviewed heads. Never open a fourth head. On the
third head:

- any unclassified finding, or any non-nit finding, terminates as
  `blocked_at_cap` — the pull request stays draft, and the terminal report
  carries every surviving structured finding;
- nits only, after every nit is fixed and required checks pass, terminates as
  `nits_fixed`.

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

Discharge then turns on where the reader sits.

- An **off-target** reader discharges once it is named with a result. This
  branch cannot repair it.
- An **on-target** reader that reads the new shape correctly discharges on that
  result.
- An **on-target** reader that reads the new shape wrong is a bug-severity
  finding of the round that checked it. It joins that round's findings, and it
  discharges on exactly one of three results, each of them an outcome gate 2
  already produces: it is repaired, it is recorded as a skipped finding, or the
  advisor refutes it. Naming the break discharges nothing on its own, and
  neither does a further round merely happening.

The list discharges once every reader on it has discharged.

A broken reader outside the review target does not block the loop and does not
widen scope. Hand it off as a reported finding. Two separate things are owed for
that hand-off, and they land at different times:

- **The round-scoped record** — what a round produces. Check the reader, record
  its result, and name it in that round's progress report. All three are done
  inside the round that checks the reader, and nothing outside that round is
  needed to complete them. This is the record gate 2 reads.
- **The termination-time disclosure** — what terminating requires. The
  ready-for-review message names every broken off-target reader and every
  skipped finding that still exists, and the pull request body carries the same
  names when the target is a pull request. A target with no pull request owes
  the ready message alone. Gate 3 enforces this at the moment the loop
  terminates; no earlier round owes it.

## Terminal outcomes

The loop emits exactly one of these terminals when it stops:

| Terminal | When |
|---|---|
| `clean` | Zero retained findings on the current head, and required checks pass |
| `nits_fixed` | Every retained finding is a nit with severity and a retained verdict, every nit is fixed, and required checks pass (including on the third head) |
| `blocked_at_cap` | Third reviewed head still holds an unclassified or non-nit finding; draft state is preserved |
| `advisor_blocked` | Classification needs the assigned advisor and that advisor is unreachable |

Every round does this round's own work first, then runs the three gates below,
in order: gate 1, then gate 2, then gate 3.

**This round's work — before the gates.** Record this round's dangerous
classification and the dangerous-round count as `N of M`; and when a shape-change
list is open, check each reader on that list and name each reader with its
result, adding any on-target reader that reads the new shape wrong to this
round's findings as *A shape change names its readers* directs. Then run the
gates.

**Gate 1 — obligations.** Gate 1 is evaluated first in the sequence, and its
answer turns on the round's open obligations alone — the findings are in hand by
now, and no content they carry changes it. Ask only: does any obligation remain
open? Two kinds exist.

- A dangerous diff that has had fewer than two full rounds.
- A posted shape-change list that no round has discharged.

Gate 1 states its answer and stops there: an obligation remains open, or none
does. It states no re-entry, no continuation, and no routing. Gate 3 is the sole
router — every path out of a round passes through it.

**Gate 2 — findings.** When `--fix` is set, load `reference\fix.md` here and
follow it for the mechanics of every fix this gate applies — the fix agent,
agent resume, the code-rules gate, skip logging, and outcome reporting. When `--fix` is
absent, apply each fix in this session yourself, and log each skip in this
round's progress report. Then take the one case that matches the round's
findings.

- Any bug-severity finding: validate each bug with an advisor before touching
  code — confirm it's real and confirm the intended fix — then fix every
  validated bug and every nit on the review target. A refuted bug removes only
  itself from the round's work; the nits are fixed either way.
- Nits only, with at least one nit present: fix all of them on the review
  target.
- No findings at all: make no edits.

Gate 2 then ends by stating one of exactly two outcomes: unresolved findings
remain, or none remain. A refuted bug is resolved. A fixed nit is resolved. A
fixed validated bug is resolved. A handed-off off-target finding is resolved once
this round has made its round-scoped record as *A shape change names its readers*
defines that record — checked, result recorded, named in this round's progress
report — whether or not the problem behind it is solved. Gate 2 reads the record
and nothing else; the termination-time disclosure belongs to gate 3.

A skipped finding — a finding deliberately not applied, because fixing it would
change intended behavior, would reach beyond the review target, or the finding
itself is judged a false positive — is resolved once its skip is logged in this
round's progress report, naming the finding and the reason it was skipped. That
report is the sink every run has, with or without `--fix`. When `--fix` is set,
the skip handling `fix.md` carries runs inside this gate and adds to this log
rather than replacing it.

Gate 3 reads that stated outcome, never a case label.

**Gate 3 — exit test.** Resolve the terminal from the table above, then stop or
continue:

- zero retained findings and required checks pass → `clean`;
- nits only (each with severity and a retained verdict), all fixed, required checks pass → `nits_fixed`;
- third head with unclassified or non-nit findings → `blocked_at_cap` (keep
  draft; report surviving findings);
- advisor needed for classification and unreachable → `advisor_blocked`;
- otherwise continue only when the reviewed-head count is still under three.

Also require, for `clean` and `nits_fixed`:

- gate 1 shows no open obligation;
- gate 2 states no unresolved findings remain;
- this round produced no edits after the gates settled.

Any other combination runs the round tail and re-enters the loop, unless the
three-head cap already forced `blocked_at_cap`.

Terminating with `clean` or `nits_fixed` carries one further condition — the
termination-time disclosure: the ready-for-review message names every broken
off-target reader and every skipped finding that still exists. When the target
is a pull request, the pull request body carries the same names; a target with
no pull request owes the ready message alone. Every surface this condition
names is written at termination — the ready message always, the pull request
body too when the target is a pull request — so each one is available to the
terminating round. A round that cannot name them does not terminate; it runs
the round tail and re-enters the loop, the same as any other non-terminating
round. With that condition met, post the proof-of-work PR comment when the
target is a PR, then run `gh pr ready` for a draft PR, or state ready
otherwise.

`blocked_at_cap` and `advisor_blocked` keep the pull request draft. They do
not run `gh pr ready`. They report every surviving structured finding.

Gate 3 points at gate 1 for the obligation answer. It does not restate the
two-round rule or the shape-reader rule; each of those keeps its one home in its
own section above.

**The round tail.** Every round runs required checks here, in the one form
*Required checks* gives: the bare command, no file paths. When this round
produced edits, stage those edits first so they enter the bare gate's scope,
then run the checks. When this round produced no edits, run the same checks.
Should those checks produce repairs, this round has produced edits — stage
them and re-run the checks.

**Commit and push are lead-owned.** Gate 2 and the round tail leave every fix
unstaged-or-staged in the working tree for the lead that owns the branch. A
fix agent, patch worker, or resumed finding agent never creates the commit and
never pushes. The lead stages, commits once per review round, and pushes after
the gates pass. Start the next round under *Each round reviews new code* only
after that lead commit lands a new head, or after a no-edit round that is
still under the three-head cap.

Do not drop findings to force ready. Without `loop`, run one review at the selected level, fix, and return every validated finding.
