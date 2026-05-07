# Stop conditions

- **Convergence** (back-to-back clean ∧ no outstanding Copilot findings
  on `current_head` ∧ `mergeable_state == "clean"` with `mergeable ==
  true` ∧ post-convergence Copilot request returned `clean` at
  `current_head`): use `update_pull_request(pullNumber=NUMBER, owner=OWNER, repo=REPO, draft=false)`. With
  `state.json`, append convergence row to
  `<TMPDIR>/pr-converge-<session_id>/converged.log` per `multi-pr-orchestration.md` §Memory; else
  skip. Report [convergence-gates.md](convergence-gates.md) (d) summary, then **omit loop pacing**
  per **Convergence** in `../workflows/schedule-wakeup-loop.md`. End all loops
  once all PRs terminal (converged or blocked).
- **Hard blocker:** API auth failure across two ticks, CI regression
  whose root cause falls outside this PR, hook rejection unresolved
  across three commits, `inline_lag_streak >= 3`, **bugteam** reports
  stuck, or post-convergence Copilot request fails to surface review on
  `current_head` after three consecutive wakeups. Report specific
  blocker and diagnosis, **omit loop pacing** per
  `../workflows/schedule-wakeup-loop.md`.
- **Hard blocker (`mergeable_state` non-clean non-dirty):**
  `mergeable_state` is `"blocked"`, `"unknown"`, or `"behind"` (required
  checks pending, branch behind base without textual conflicts, or
  GitHub indeterminate). Investigate before retrying; `rebase` skill
  handles `"dirty"` (textual conflicts) only. Report specific
  `mergeable_state`, **omit loop pacing**.
- **User stops loop:** "stop the converge loop" → **omit loop pacing**
  per `../workflows/schedule-wakeup-loop.md`.
