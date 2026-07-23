# Loop until clean or blocked

**`loop` means act now.** Use this file for every effort level after one review cycle. Re-run that same level procedure on each new head.

## Act without asking

`loop` on the hub command authorizes the full cycle. After the level procedure returns findings, take the matching branch below immediately.

Do not ask whether to fix, which nits to keep, whether to commit or push, or whether to re-review. Do not open a plan fork. Do not end the turn on a recommendation.

Report progress while you work. Stop for the user only on a terminal outcome below.

## Scope stays narrow

Auto-fix only verified findings on the review target. Leave deferred PR-body follow-ups and unrelated refactors alone.

House git gates still apply: draft PR, verified commit, one commit per round, proof-of-work when required. Satisfy them by doing the steps. Do not ask permission to do them.

## How to class each finding

Use the finding’s verified `severity` when the level emits one.

A finding is a `nit` only when that severity is `nit`. Runtime-correctness, security, data-loss, compatibility, and every other non-nit finding is a `bug`.

If the level emits no severity (for example untagged `low` lines), treat every non-empty finding as a `bug`.

## Terminal outcomes

Repeat the same-level review/fix cycle until one of these holds:

- **Clean.** Findings are `[]` or `(none)`. Post the proof-of-work PR comment when the target is a PR. Run `gh pr ready` for a draft PR; otherwise state ready.
- **Nits only.** Every surviving finding is severity `nit`. Fix all of them on the PR branch worktree (or the review target). Run required checks. Commit once per loop round. Push. Run the same effort level on the new head. Repeat until clean, then mark ready as above.
- **Any bug.** Return every validated finding (bugs and nits). Stop the loop. Do not mark ready. Do not ask whether to continue. Wait for a new user instruction.

Do not drop findings to force ready. Without `loop`, run one review at the selected level and return every validated finding.
