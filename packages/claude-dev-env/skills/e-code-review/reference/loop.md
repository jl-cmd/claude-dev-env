# Loop until clean

## Act

`loop` on the hub command authorizes the full cycle. After the effort level procedure returns findings, take the matching branch below immediately.

Do not ask whether to fix, which nits to keep, whether to commit or push, or whether to re-review. Do not open a plan fork. Do not end the turn on a recommendation.

Report progress while you work. Stop for the user only on a terminal outcome below.

## Scope stays narrow

Auto-fix only verified findings on the review target. Leave deferred PR-body follow-ups and unrelated refactors alone.

## How to class each finding

Use the finding's verified `severity` when the level emits one.

A finding is a `nit` only when that severity is `nit`. Runtime-correctness, security, data-loss, compatibility, and every other non-nit finding is a `bug`.

If the level emits no severity (for example untagged `low` lines), consult your advisor to determine classification.

## Required checks

"Run required checks" means: run `~/.claude/_shared/pr-loop/scripts/code_rules_gate.py --repo-root <repo root> <changed/added files>` against every file changed or added in the round. On any violation, fix it and re-run the exact same command again — repeat until it reports clean.

## Terminal outcomes

Repeat the same-level review/fix cycle until one of these holds:

- **Clean.** Findings are `[]` or `(none)`. Post the proof-of-work PR comment when the target is a PR. Run `gh pr ready` for a draft PR; otherwise state ready.
- **Nits only.** Every surviving finding is severity `nit`. Fix all of them on the review target. Run required checks. Commit once per loop round. Push. Consider this clean — post the proof-of-work PR comment and mark ready as in the Clean branch above.
- **Any bug.** Validate each bug-severity finding with an advisor before touching code — confirm it's real and confirm the intended fix. Then fix all validated findings (bugs and nits) on the review target. Run required checks. Commit once per loop round. Push. Run the same effort level on the new head. Repeat until clean, then mark ready as above.

Do not drop findings to force ready. Without `loop`, run one review at the selected level, fix, and return every validated finding.
