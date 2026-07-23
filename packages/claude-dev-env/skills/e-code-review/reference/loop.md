# Optional loop mode

Applies when the hub invocation includes `loop`, for **any** effort level
(`low`, `xhigh`, `max`). The hub loads this file after one cycle of the
selected level procedure; each re-review re-runs that same level procedure.

## Authorization and autonomy

When the hub invocation includes `loop`, that invocation authorizes action.
After the level procedure produces a verified findings set, execute the
matching branch immediately. Do not ask whether to fix, which nits to keep,
whether to commit or push, or whether to re-review. Do not open a plan fork or
end the turn on a recommendation. Report progress only while working; the next
user-facing stop is a terminal outcome below.

No mid-loop confirmation questions, “should I fix these?”, “want me to push?”,
or option menus. Auto-fix only verified findings on the review target; do not
expand into deferred PR-body follow-ups or unrelated refactors. House git gates
still apply (draft PR, verified commit, one commit per round, proof-of-work
when required)—satisfy them by doing the steps, not by asking permission.

## Severity for loop branches

- Prefer the finding's verified `severity` when the level emits one (`bug` or
  `nit`).
- A finding is a `nit` only when its verified severity is `nit`.
  Runtime-correctness, security, data-loss, compatibility, and every other
  non-nit finding is a `bug`.
- When the level does not emit severity (for example `low` untagged lines),
  treat every non-empty finding as a `bug`.

## Terminal outcomes

Repeat the level's review/fix cycle until one of these:

- **Clean** — review returns no findings (`[]` or `(none)`). Mark ready: post
  the proof-of-work PR comment when the target is a PR, then run `gh pr ready`
  for a draft PR; otherwise state ready.
- **Nits only** — every surviving finding is severity `nit`. Fix all of them on
  the PR branch worktree (or the review target), run required checks, commit
  (one commit per loop round), push, and run another full review at the
  **same** effort level on the new head. Repeat until clean, then mark ready as
  above.
- **Any bug** — any surviving finding is severity `bug`. Return every validated
  finding (bugs and nits), stop the loop, do not mark ready, and do not ask
  whether to continue; wait for a new user instruction.

Do not discard findings to force a ready outcome. Without `loop`, run one
review at the selected level and return every validated finding; do not apply
this convergence behavior.
