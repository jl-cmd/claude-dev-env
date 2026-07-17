# Stop conditions

The workflow ends one of two ways: converged (PR marked ready) or blocked. A
blocker exit returns `{ converged: false, rounds, finalSha, blocker }`, and the
skill still runs teardown (revoke permissions, final report).

## Blockers (end the run short of ready)

- **Budget stop** — on `pacer=workflow`, the workflow's `budget` API is the
  pacing signal: when a usage target is set, `converge.mjs` checks
  `budget.remaining()` before each round and stops at the round boundary when
  one full round (three parallel lenses + one fix commit + re-verify) does not
  fit. The run returns `blocker: "budget"` with the run id; resume with
  `Workflow({scriptPath, resumeFromRunId})` — completed rounds replay from the
  journal. The workflow never starts a round the budget cannot finish: a
  half-run round records nothing resumable and replays dirty. On
  `pacer=portable`, stop at a tick boundary when the session cannot cover a
  full clean tick; write handoff and resume with `/autoconverge <PR URL>`
  ([`../../_shared/pr-loop/portable-driver.md`](../../_shared/pr-loop/portable-driver.md)).
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
  reaches the terminal Bugbot, Copilot, Codex, and convergence gates.
- **Static-sweep stalled** — the deterministic static sweep (`code_rules_gate.py
  --base origin/main`, `ruff`, `mypy`, stem-matched `pytest`) raises gate or test
  failures the fixer cannot clear on the current HEAD, so HEAD does not move. The
  reading lenses never run on a sweep-dirty HEAD, so the run ends with a
  static-sweep stall `blocker` naming the failure count and the stalled HEAD
  rather than looping to the iteration cap.
- **Mark-ready failed** — the convergence check passes but the mark-ready step
  cannot confirm the PR left draft state (`gh pr ready` errored, or the draft
  re-query still reports true). The workflow does not report `converged: true`;
  the run ends with a `blocker` naming the failed ready transition.
- **No review lens reviewed HEAD** — a round can end with no lens having reviewed
  the HEAD three ways: the preflight resolves no SHA, every lens agent dies, or
  every lens is down or disabled. A single such round retries on the next round.
  Three consecutive no-lens-reviewed rounds (any mix of the three causes) reach
  `CONFIG.maxConsecutiveNoLensRounds` and stop the run with a `blocker` that names
  the consecutive count and only the causes that actually occurred, rather than
  looping to the iteration cap. Any round in which at least one lens reviews the
  HEAD resets the consecutive count.

## Not a blocker (the run continues)

Each reviewer-down condition below skips its own convergence-check gate. The flag and the matching `CLAUDE_REVIEWS_DISABLED` token for each condition are the single flag-per-condition table in [`../../reviewer-gates/SKILL.md`](../../reviewer-gates/SKILL.md) § "Convergence-check bypass flags"; the token carries the bypass into the mark-ready blocker hook's no-flag re-check.

- **Clean-audit post bypassed** — every review lens is clean on HEAD, but the
  environment refuses the CLEAN bugteam review post (the `post_audit_thread.py`
  post is denied, errors, or its agent never runs). The lens results already show
  this HEAD is clean, so the CLEAN post is a record-keeping artifact, not the
  safety-bearing gate. The run records a `cleanAuditNote` naming the HEAD and the
  reason, logs the bypass, and proceeds to the terminal Bugbot gate — the same
  shape as the Bugbot-down and Copilot-down paths. The convergence check runs with
  `--bugteam-post-blocked` so its bugteam CLEAN-review gate is skipped and the run
  closes on the remaining signals. A round where no lens actually reviewed HEAD is
  separate: that re-converges under the no-review-lens rule above, since no lens
  grounded a post.
- **Terminal Bugbot gate down or disabled** — the terminal Bugbot gate runs once
  the internal lenses are clean. When Cursor Bugbot is off for the run (the
  default unless `CLAUDE_REVIEWS_ENABLED` lists `bugbot`) or opted out via
  `CLAUDE_REVIEWS_DISABLED`, the gate spawns no agent and passes to the Copilot
  gate with `bugbotDown` set. When Bugbot is enabled but never produces a check
  run or review after the gate poll budget, the gate returns down the same way.
  The run continues, and the convergence check runs with `--bugbot-down` so its
  Bugbot gate is bypassed.
- **Copilot down or out of quota** — when Copilot posts an out-of-usage notice on
  the current HEAD (the user who requested the review reached their quota limit)
  rather than a code review, or surfaces no review at all after the configured cap, the
  Copilot gate returns `down: true`. The run logs a notice, sets `copilotDown`,
  and proceeds to the Codex gate. The later convergence check receives
  `--copilot-down` (the Copilot review gate and the pending-requested-reviews
  gate bypassed), then mark-ready. `copilotNote` records the bypass for the
  final report.
- **Terminal Codex gate skipped or down** — the conditional-required Codex gate
  runs after Bugbot and Copilot. When `CLAUDE_REVIEWS_DISABLED` lists `codex`
  (`reviews_disabled.py --reviewer codex` exit 0), the gate sets `codexDown` and
  advances with no review. When the weekly usage probe reports `percent_left`
  null or at/below the shared threshold (`is_codex_review_required` false), the
  gate skips without a stamp; the convergence check applies the same rule. When
  the wrapper classifies `codex_down`, the gate sets `codexDown` and advances.
  A clean required run stamps `codexCleanAt` for `--codex-clean-at`. Non-code-standard
  findings re-enter CONVERGE through the existing fix path. Standards-only findings
  defer a follow-up, stamp `codexCleanAt`, and advance to FINALIZE (no fix push).
- **A lens agent dies** — when one parallel reading lens returns null (a terminal
  agent failure), the round proceeds on the surviving lenses. A real defect it
  would have caught surfaces in a later round or at the convergence check. A dead
  terminal Bugbot gate agent (null result) is a retry rather than an approval, so
  the gate re-runs on the same HEAD rather than treating a dead agent as a clean
  Bugbot verdict.
- **Every lens agent dies (a single round)** — when all three parallel reading
  lenses return null in the same round, the round is a failure, not a clean: the
  workflow posts no CLEAN bugteam artifact and does not advance to the terminal
  gates. It re-resolves HEAD and retries on the next round. This is a
  no-lens-reviewed round, so consecutive occurrences are bounded by the
  no-review-lens cap in the blockers above, not just the iteration cap.

## User stop

Stopping the background workflow (`TaskStop`, or the user halting the run) ends
it where it stands. Re-launching `/autoconverge` starts a fresh run; the
workflow journal allows resuming the prior run from its last completed step with
`Workflow({ scriptPath, resumeFromRunId })`.
