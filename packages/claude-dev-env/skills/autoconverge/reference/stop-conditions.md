# Stop conditions

The workflow ends one of two ways: converged (PR marked ready) or blocked. A
blocker exit returns `{ converged: false, rounds, finalSha, blocker }`, and the
skill still runs teardown (revoke permissions, final report).

## Blockers (end the run short of ready)

- **Iteration cap** — 20 loop iterations pass without a full convergence-check
  pass. The iteration counter increments on every pass through any phase, so a
  convergence-check gate that no round can clear (for example a `mergeable_state`
  stuck at `blocked`, `behind`, or `unknown` that a rebase does not fix) and a
  Copilot gate agent that keeps dying and retrying on the same HEAD both reach
  the cap this way. `blocker` reports `iteration cap reached`.
- **Fix stalled** — the fix lens reports no push (`pushed: false`) without
  resolving every finding thread, returns a SHA equal to the prior HEAD on a
  case-folded common prefix (a full or abbreviated SHA of the unchanged commit
  both count), or returns null for a round's findings. HEAD did not move and the
  threads were not all resolved, so the next round would re-raise the same
  findings. The run ends with a `blocker` that names the finding count and the
  stalled HEAD. A round whose every finding carries no GitHub thread
  (`replyToCommentId: null` on each) and whose fix reports
  `resolvedWithoutCommit: true` is also a stall: it moves no code and resolves no
  thread, so re-converging on the unchanged HEAD would loop the same finding to
  the iteration cap. The `blocker` names the in-memory finding count and the
  stalled HEAD. An all-stale round that makes no commit but resolves every
  finding thread (`resolvedWithoutCommit: true` with at least one thread-bearing
  finding) is not a stall — the run re-converges on the unchanged HEAD and
  reaches the Copilot and convergence gates.
- **Mark-ready failed** — the convergence check passes but the mark-ready step
  cannot confirm the PR left draft state (`gh pr ready` errored, or the draft
  re-query still reports true). The workflow does not report `converged: true`;
  the run ends with a `blocker` naming the failed ready transition.
- **Clean-audit post blocked** — every review lens is clean on HEAD, but the
  CLEAN bugteam review cannot be posted (the `post_audit_thread.py` post is
  denied, errors, or its agent dies). The convergence gate's bugteam-review
  check can never pass without that CLEAN review, so the run stops rather than
  re-converge to the iteration cap. The `blocker` names the post failure and the
  HEAD. Unblock by allowing `post_audit_thread.py` with a Bash permission rule,
  or post the CLEAN review by hand, then re-run.

## Not a blocker (the run continues)

- **Bugbot down** — when Cursor Bugbot is opted out, or never produces a check
  run or review after the lens poll budget, the Bugbot lens returns `down: true`.
  The run continues, and the convergence check runs with `--bugbot-down` so its
  Bugbot gate is bypassed.
- **Copilot down or out of quota** — when Copilot posts an out-of-usage notice on
  the current HEAD (the user who requested the review reached their quota limit)
  rather than a code review, or surfaces no review at all after the configured cap, the
  Copilot gate returns `down: true`. The run logs a notice, runs the convergence
  check with `--copilot-down` (the Copilot review gate and the
  pending-requested-reviews gate bypassed), and marks the PR ready. `copilotNote`
  records the bypass for the final report.
- **A lens agent dies** — when one parallel lens returns null (a terminal agent
  failure), the round proceeds on the surviving lenses. A real defect it would
  have caught surfaces in a later round or at the convergence check. A dead
  Bugbot lens (null result) counts as down for that HEAD, so the convergence
  check runs with `--bugbot-down` rather than demanding a Bugbot verdict the
  dead agent never produced.
- **Every lens agent dies** — when all three parallel lenses return null in the
  same round, the round is a failure, not a clean: the workflow posts no CLEAN
  bugteam artifact and does not advance to the Copilot gate. It re-resolves HEAD
  and retries on the next round, still bounded by the iteration cap.

## User stop

Stopping the background workflow (`TaskStop`, or the user halting the run) ends
it where it stands. Re-launching `/autoconverge` starts a fresh run; the
workflow journal allows resuming the prior run from its last completed step with
`Workflow({ scriptPath, resumeFromRunId })`.
