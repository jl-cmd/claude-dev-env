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
any improvement that did not land. The run result's `reuseNote` records what
landed.

## The round loop

The workflow holds five states and moves between them until the PR is ready or
a blocker ends the run. A single iteration counter increments on every pass
through any phase and caps the whole run at 20 loop iterations; the round counter
tracks CONVERGE passes only and is never the cap. The internal lenses drive the
code to clean first; the external reviewers run only after that, as terminal
confirmation gates that are expected to return zero.

**CONVERGE** (one round = a static sweep then one parallel lens sweep):

1. Resolve the current PR HEAD SHA. The same preflight step also fetches
   `origin/main` once for the round and enumerates the diff — the
   `git diff --name-status origin/main...HEAD` changed-file list and the
   `git diff --stat` diffstat — and carries both into the round.
2. Run the **static-sweep lens** on that HEAD: a deterministic pass that runs the
   CODE_RULES gate (`code_rules_gate.py --base origin/main`), `ruff`, `mypy`, and
   stem-matched `pytest` over the changed files, mapping each failure to a
   finding. It uses local commands only, so it runs in any session. When the sweep
   raises a finding, one `clean-coder` fixes it through the same fix flow below and
   the round re-runs, so the reading lenses only ever review sweep-clean code.
3. Run three reading lenses in parallel on that HEAD, each over the full
   `origin/main...HEAD` diff. Each lens receives the preflight's changed-file
   list and diffstat and reads only the files it needs from that list rather than
   re-deriving the diff; each lens forms its own review judgment.
   - **Code-review lens** — a correctness-focused review pass (`code-quality-agent`),
     report-only workflow agent — see runCodeReviewLens in workflow/converge.mjs for its configuration.
     The built-in `/code-review` surface is a separate path owned by the
     **claude-review** skill
     ([`../../claude-review/SKILL.md`](../../claude-review/SKILL.md)):
     full-diff `/code-review xhigh --fix` via `invoke_code_review.py`.
     On `pacer=workflow`, the workflow lens runs inside `converge.mjs`.
     On `pacer=portable`, the continuous driver uses the pr-converge CODE_REVIEW
     phase, which invokes claude-review / `invoke_code_review.py`
     ([`../../_shared/pr-loop/portable-driver.md`](../../_shared/pr-loop/portable-driver.md);
     [`../../pr-converge/reference/per-tick.md`](../../pr-converge/reference/per-tick.md)).
   - **Bug-audit lens** — the bug-audit (`code-quality-agent`) applying the
     shared A–P rubric from `_shared/pr-loop/audit-contract.md`, then its
     adversarial second pass, and the doc-parity, test-assertion, and
     PR-description lanes from `_shared/pr-loop/precatch-rubric.md`, reporting
     findings without editing.
   - **Self-review lens** — the semantic parity pass (`code-quality-agent`) that
     reads `_shared/pr-loop/precatch-rubric.md` and covers doc-vs-code parity,
     test-assertion completeness, and PR-description-vs-diff parity, reporting
     findings without editing.
4. Dedup findings across the three lenses by file, line, and title. A collision
   keeps the most severe duplicate's severity (P0 > P1 > P2), unions the detail
   text, and collects every distinct bot thread id so the fix lens resolves all
   colliding threads.
5. **Any findings** → one `clean-coder` applies every fix per the
   `pr-fix-protocol` skill (`../../pr-fix-protocol/SKILL.md`): a single
   test-first commit, a push, then a reply and resolve on each finding that
   carries a GitHub review thread. Before its turn ends, the edit step dry-runs
   the CODE_RULES commit gate (`code_rules_gate.py --staged`) over its staged
   changes and keeps fixing until that gate would accept the commit, so the
   later commit step never hits a gate rejection. A round progresses when the
   fix lens lands a push that moves HEAD, or when every finding was already
   addressed so no code change is needed yet each finding thread is still
   resolved (the fix lens reports `resolvedWithoutCommit` and the run
   re-converges on the unchanged HEAD). A round whose fix lens reports neither
   a moved-HEAD push nor a full thread-resolution ends the run with a
   fix-stalled blocker. The next round re-verifies on the current HEAD.
6. **Zero findings on a stable HEAD** → post the CLEAN bugteam audit artifact
   for that HEAD, then move to the terminal Bugbot gate.

A round whose findings are ALL code-standard violations (pure CODE_RULES/style,
no behavioral impact) passes for convergence purposes: the workflow files a
follow-up issue listing the findings, opens a draft environment-hardening PR
(hooks/rules that block those violation classes at Write/Edit time), resolves
any bot threads with a deferral note, and reports the deferral in
`standardsNote`. The hardening PRs land in the run result's `deferredPrs` list.

**BUGBOT** gate (terminal external confirmation):

- Runs once the internal lenses are clean. When Bugbot is off for the run — the
  default unless `CLAUDE_REVIEWS_ENABLED` lists `bugbot` — opted out via
  `CLAUDE_REVIEWS_DISABLED`, or unreachable, the gate spawns no agent and moves
  to the Copilot gate with `bugbotDown` set.
- Otherwise drive Cursor Bugbot to a verdict on HEAD (trigger and poll its CI
  check run when needed).
- Bugbot findings → fix them and return to CONVERGE on the new HEAD.
- Bugbot clean or approved → move to the Copilot gate.
- Bugbot down after the poll cap → move to the Copilot gate with `bugbotDown` set.

**COPILOT** gate (terminal external confirmation):

- Request a Copilot review on HEAD (skipping a duplicate request), then poll up
  to the configured cap, 360 seconds apart.
- Copilot findings → fix them and return to CONVERGE on the new HEAD.
- Copilot clean or approved → move to the Codex gate.
- Copilot down or out of quota (an out-of-usage notice, or no review after the
  configured cap) → log a notice and move to the Codex gate with the Copilot gate
  bypassed.

**CODEX** gate (conditional-required terminal confirmation):

- Runs after Bugbot and Copilot. Honors `reviews_disabled.py --reviewer codex`,
  the weekly usage probe via `is_codex_review_required` (shared threshold
  constant — no inline percent), and the wrapper's `codex_down` class.
- Opt-out token or `codex_down` → set `codexDown`, no stamp, move to the
  convergence check with `--codex-down`.
- Usage at/below threshold or null → skip with no stamp; the machine checklist
  applies the same rule.
- Above threshold → run the codex-review wrapper against the PR base branch.
  Non–code-standard findings → fix and return to CONVERGE.
  Standards-only findings → defer a follow-up, stamp `codexCleanAt`, and move to the
  convergence check (no fix push).
  Clean → stamp `codexCleanAt` and pass `--codex-clean-at` into the convergence check.

**Convergence check**:

- One agent runs `check_convergence.py` and, on a full pass, marks the PR ready
  (`draft=false`) in the same turn, ending the run. A failure returns to CONVERGE
  so the next round addresses the failing gate; the repair path re-runs this same
  check, and only a passing check marks the PR ready.

## Model tiers

Each spawned agent runs on the model and effort its role needs, so the run spends
the strongest model only where judgment is dense:

- **sonnet** — the deterministic static-sweep lens, and the verify,
  commit, and recovery steps that clear a commit-gate or verdict rejection.
- **opus** — the reading lenses (code-review, bug-audit, self-review,
  reuse), the terminal Bugbot gate, and the code-editing steps that fix findings
  (fix-edit, conflict-edit, repair-edit, standards-edit).
- **haiku** — the mechanical probes: preflight, the Copilot gate, the Codex
  gate, the CLEAN-audit post, and the convergence check.

## Full-diff rule

Every lens, every round, reviews the full `origin/main...HEAD` diff — every file
the PR touches. A lens that scopes to recent commits, a single file, or a
bugbot-flagged path does not satisfy the round; its clean verdict is not a clean.

The portable built-in review path (claude-review / `invoke_code_review.py`) follows
the same full-diff rule; see
[`../../claude-review/reference/full-diff-and-clean-stamp.md`](../../claude-review/reference/full-diff-and-clean-stamp.md).

## The ready definition

`check_convergence.py` (`pr-converge/scripts/check_convergence.py`) is the single
source of truth for readiness. Ready means the script exits `0` and prints:

```
All pre-conditions met — PR is ready to mark ready.
```

The script re-derives every condition from GitHub and prints one PASS/FAIL line
per label. The exact printed labels (script order) live in
[`pr-converge/reference/convergence-gates.md`](../../pr-converge/reference/convergence-gates.md)
§ (f) Mark ready and report — the seven-label block under "Exact printed labels".

The script has no Claude APPROVED review gate. Agent-side checks (Claude
reviewer presence, broader unresolved-thread sweeps) sit outside this machine
checklist.

## Audit-trail design

Bugbot and Copilot post their own review threads, which the fix lens replies to
and resolves. Codex findings are local to the gate (no GitHub review thread) and
enter the same fix path with `replyToCommentId: null`. The bug-audit lens keeps
its findings in memory across the round and posts only the terminal CLEAN bugteam
review once every lens is clean on a stable HEAD — that single artifact is what
gate 3 reads. This keeps thread churn to the threads the bots raise themselves.
