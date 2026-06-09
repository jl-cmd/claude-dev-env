# Convergence — round shape and the ready definition

## The round loop

The workflow holds three states and moves between them until the PR is ready or
a blocker ends the run. A single iteration counter increments on every pass
through any phase and caps the whole run at 20 loop iterations; the round counter
tracks CONVERGE passes only and is never the cap.

**CONVERGE** (one round = one parallel sweep):

1. Resolve the current PR HEAD SHA.
2. Run three lenses in parallel on that HEAD, each over the full
   `origin/main...HEAD` diff:
   - **Bugbot lens** — drive Cursor Bugbot to a verdict on HEAD (trigger and
     poll its CI check run when needed) and return its findings, or mark itself
     down when Bugbot is opted out or unreachable.
   - **Code-review lens** — a correctness-focused review pass (`code-quality-agent`)
     that reports findings without editing.
   - **Bug-audit lens** — the bug-audit (`code-quality-agent`) applying the
     shared A–P rubric from `bugteam/reference/audit-contract.md`, reporting
     findings without editing.
3. Dedup findings across the three lenses by file, line, and title. A collision
   keeps the most severe duplicate's severity (P0 > P1 > P2), unions the detail
   text, and collects every distinct bot thread id so the fix lens resolves all
   colliding threads.
4. **Any findings** → one `clean-coder` applies every fix in a single test-first
   commit, pushes, then replies to and resolves each finding that carries a
   GitHub review thread. A round progresses when the fix lens lands a push that
   moves HEAD, or when every finding was already addressed so no code change is
   needed yet each finding thread is still resolved (the fix lens reports
   `resolvedWithoutCommit` and the run re-converges on the unchanged HEAD). A
   round whose fix lens reports neither a moved-HEAD push nor a full
   thread-resolution ends the run with a fix-stalled blocker. The next round
   re-verifies on the current HEAD.
5. **Zero findings on a stable HEAD** → post the CLEAN bugteam audit artifact
   for that HEAD, then move to the Copilot gate.

**COPILOT** gate:

- Request a Copilot review on HEAD (skipping a duplicate request), then poll up
  to three times, 360 seconds apart.
- Copilot findings → fix them and return to CONVERGE on the new HEAD.
- Copilot clean or approved → move to the convergence check.
- No review after three polls → blocker.

**Convergence check**:

- Run `check_convergence.py`. A full pass marks the PR ready (`draft=false`) and
  ends the run. A failure returns to CONVERGE so the next round addresses the
  failing gate.

## Full-diff rule

Every lens, every round, reviews the full `origin/main...HEAD` diff — every file
the PR touches. A lens that scopes to recent commits, a single file, or a
bugbot-flagged path does not satisfy the round; its clean verdict is not a clean.

## The ready definition

`check_convergence.py` is the single source of truth for readiness. It re-derives
every condition from GitHub and marks the PR ready only when all of these hold on
the current HEAD:

1. Bugbot CI check run is completed with a success or neutral conclusion
   (bypassed when Bugbot is opted out or proved unreachable this run).
2. The Bugbot review body on HEAD reports no findings (checked when a Bugbot
   review is present).
3. A CLEAN bugteam audit review sits on HEAD.
4. The Copilot review on HEAD is clean or approved.
5. Zero unresolved bot review threads anywhere on the PR — counting Cursor,
   Claude, and Copilot authored threads where `isResolved` is false (`isOutdated`
   threads are excluded by the gate, but the fix lens still verifies and resolves
   them during the round).
6. The PR is mergeable (`mergeable` true and `mergeable_state` clean).
7. No requested reviewers are still pending.

## Audit-trail design

Bugbot and Copilot post their own review threads, which the fix lens replies to
and resolves. The bug-audit lens keeps its findings in memory across the round
and posts only the terminal CLEAN bugteam review once every lens is clean on a
stable HEAD — that single artifact is what gate 3 reads. This keeps thread churn
to the threads the bots raise themselves.
