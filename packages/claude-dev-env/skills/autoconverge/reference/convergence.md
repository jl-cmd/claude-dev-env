# Convergence — round shape and the ready definition

## Pre-flight: clear merge conflicts

Before the first round, the workflow checks once whether the PR branch conflicts
with `origin/main`. When GitHub reports a conflict (`mergeable` false or
`mergeable_state` dirty), one `clean-coder` rebases the branch onto `origin/main`
and resolves every conflict — gated the same way as every other code change: the
edit leaves the rebase in the working tree, a `code-verifier` binds a verdict to
it, and the commit step force-pushes with lease. The bug checks then run on a
conflict-free diff.

A PR that merges cleanly skips the rebase. A conflict that surfaces mid-run, when
`origin/main` advances during a later round, is caught by the convergence repair
at the end of the loop, which also rebases.

## Reuse pass (runs after the conflict pre-flight, before convergence)

One reuse lens (`code-quality-agent`) reviews the full `origin/main...HEAD` diff
for code that re-implements behavior the repository already provides. It reports a
reuse improvement only when all three criteria hold together, and omits any case
where even one is in doubt:

1. **Certain** — an existing symbol or module unquestionably covers the new
   code's behavior, cited at `file:line`.
2. **Behaviorally the same** — swapping the new code for the existing one
   changes no observable behavior: same inputs, outputs, side effects, and
   error handling.
3. **Autonomously implementable** — the replacement is a mechanical edit (import
   and call the existing symbol, drop the duplicate) needing no product
   decision and no human judgment.

The lens reports without editing. Each qualifying improvement runs through the
same edit → verify → commit fix flow the rounds use, landing in one verified
commit before convergence begins. The pass is best-effort: when no case clears
all three criteria the run proceeds straight to convergence. Whatever the reuse
pass surfaces also joins the round findings, so the code-review lens re-checks
any improvement that did not land.

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
   GitHub review thread. Before its turn ends, the edit step dry-runs the
   CODE_RULES commit gate (`code_rules_gate.py --staged`) over its staged
   changes and keeps fixing until that gate would accept the commit, so the
   later commit step never hits a gate rejection. A round progresses when the fix lens lands a push that
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
  to the configured cap, 360 seconds apart.
- Copilot findings → fix them and return to CONVERGE on the new HEAD.
- Copilot clean or approved → move to the convergence check.
- Copilot down or out of quota (an out-of-usage notice, or no review after the
  poll cap) → log a notice and move to the convergence check with the Copilot gate
  bypassed.

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
4. The Copilot review on HEAD is clean or approved (bypassed when Copilot is down
   or out of quota this run).
5. Zero unresolved bot review threads anywhere on the PR — counting Cursor,
   Claude, and Copilot authored threads where `isResolved` is false (`isOutdated`
   threads are excluded by the gate, but the fix lens still verifies and resolves
   them during the round).
6. The PR is mergeable (`mergeable` true and `mergeable_state` clean).
7. No requested reviewers are still pending (bypassed when Copilot is down or out
   of quota this run).

## Audit-trail design

Bugbot and Copilot post their own review threads, which the fix lens replies to
and resolves. The bug-audit lens keeps its findings in memory across the round
and posts only the terminal CLEAN bugteam review once every lens is clean on a
stable HEAD — that single artifact is what gate 3 reads. This keeps thread churn
to the threads the bots raise themselves.
