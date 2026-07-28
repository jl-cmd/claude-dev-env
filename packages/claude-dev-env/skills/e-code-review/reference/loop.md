# Loop until clean

## Act

`loop` on the hub command authorizes the full cycle. After the effort level procedure returns findings, take the matching branch below immediately.

Do not ask whether to fix, which nits to keep, whether to commit or push, or whether to re-review. Do not open a plan fork. Do not end the turn on a recommendation.

Report progress while you work. Stop for the user only on a terminal outcome below.

## Where fixes come from

When `--fix` is also set, each round's fix pass runs `reference\fix.md`
(relative to this skill's folder) — it owns which agent applies each fix, the
commit gate, skip logging, and outcome reporting. Apply the branch rules below
on top of it: they decide whether a round fixes, commits, pushes, and
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

## A shape change names its readers

When a repair changes a key, an identifier format, or a data shape, list every
reader of the shape it changed and state how each one reads the new shape. The
list goes in the round's progress report. The next round's review checks each
named reader against the new shape.

## Terminal outcomes

Repeat the same-level review/fix cycle until one of these holds:

- **Clean.** Findings are `[]` or `(none)`, every dangerous diff has had its two full rounds, and where a round posted a shape-change list, a following round has checked every reader on it. Post the proof-of-work PR comment when the target is a PR. Run `gh pr ready` for a draft PR; otherwise state ready.
- **Nits only.** Every surviving finding is severity `nit`. Fix all of them on the review target, then run the round tail.
- **Any bug.** Validate each bug-severity finding with an advisor before touching code — confirm it's real and confirm the intended fix. Fix all validated findings, bugs and nits, on the review target, then run the round tail.

**The round tail.** Run required checks. Commit once per loop round. Push. Start the next round under *Each round reviews new code*. Repeat until clean, then mark ready as the Clean branch names.

Do not drop findings to force ready. Without `loop`, run one review at the selected level, fix, and return every validated finding.
