---
name: pr-converge
description: >-
  Loops Cursor Bugbot, a code review, a bug audit, and Copilot on the current
  PR, applying TDD fixes until all are clean on one HEAD. Use when the user says
  '/pr-converge', 'drive PR to convergence', 'loop bugbot and bugteam', 'babysit
  bugbot and bugteam', 'until both are clean', or 'converge this PR'.
---

# PR Converge

One tick per invocation. A code-review ↔ bugteam ↔ Bugbot ↔ Copilot loop on
a draft PR: the internal code-review and bugteam passes drive the code to clean
first, then Cursor Bugbot and Copilot run as terminal confirmation gates, until
all are clean on the same `HEAD` and mergeable.

## Transport check (before any GitHub step)

Run `command -v gh`; when it succeeds, run `gh auth status`; once the PR
scope is resolved, run `gh api repos/<owner>/<repo> --jq .permissions.push`
and take `true` as the pass. When any check fails, run the
`pr-loop-cloud-transport` skill first and route every `gh` operation in this
skill through its substitution matrix.

## Pre-flight

Pause and physically scan the tool list at the top of this conversation
for the literal string `ScheduleWakeup`. If you see it, proceed. If the
string is absent after scanning, report `pr-converge requires
ScheduleWakeup; aborting` and stop.

Call `EnterWorktree` with no arguments before any API call, file read, or
edit. Agent-view sessions start in the shared checkout. While Write/Edit
tools auto-isolate on first use, Bash calls (`gh`, `git`) do not trigger
isolation and will modify shared state. This step is mandatory — do not
proceed to any state-modifying operation until the working directory
contains `.claude/worktrees/`. If `EnterWorktree` fails, report the failure
and stop; do not continue in place.

`EnterWorktree` isolates the session's **own** repo. When the PR under
convergence shares that repo, its worktree is where the CODE_REVIEW phase
runs. When the PR lives in a different repo, `EnterWorktree` cannot
re-root into it; Step 1.5 resolves a **PR worktree** — a checkout of the
PR's repo on its head branch — and routes the working directory into it.
Routing the working directory into the PR's repo is routine and
automatic, never a fork to pause on. The Pre-flight `.claude/worktrees/`
gate covers the session repo's own isolation; for a cross-repo PR the
working directory routes into the PR's repo for local work and returns to
the session worktree before teardown. See
[`reference/per-tick.md` § Step 1.5](reference/per-tick.md).

## Resume from a prior run

Before Step 0, check
`~/.claude/runtime/pr-loop/bugteam-pr-<PR number>/handoff.json`. When
`$CLAUDE_JOB_DIR/pr-converge-state.json` is absent but that handoff exists, seed
`phase`, `tick_count`, and the clean-at SHAs from the run's `state-copy.json`, so
a fresh session continues where the last one stopped rather than restarting at
CODE_REVIEW.

## Copilot quota pre-check (start of run)

On the first tick, apply the `reviewer-gates` skill's Copilot quota gate
(`../reviewer-gates/SKILL.md` § Gate 2) — once per run, never per tick. The
flag lives in `pr-converge-state.json` as `copilot_down`, and every tick reads
it. While `copilot_down` is true, the tick skips all Copilot work — no fetch,
no request, no poll, no agent — and exports
`CLAUDE_REVIEWS_DISABLED="copilot"` in that tick's shell before
`check_convergence.py`, so the check bypasses the Copilot review gate and the
pending-requested-reviews gate and the run still marks ready on the remaining
signals.

## Copilot findings — tier, verify, then route

The Copilot step tiers each finding it surfaces. A **self-healing** finding is
pure style, type hints, misplaced or unused imports, formatting, magic-value
extraction, a test-only change, a doc-or-description vs code mismatch, or code
de-duplication — a fix that cannot change observable runtime behavior for
production callers. Self-healing findings flow into the existing fix tick and
count toward convergence, with no user alert. The tick-paced loop holds them
naturally: the fix lands on `current_head`, the next tick re-checks, and the run
converges when the Copilot step is clean.

A **code-concern** finding is behavior-changing or needs a product decision:
logic or correctness, security, data handling, error-handling semantics, or
concurrency. Tier a finding as code-concern whenever the tier is in doubt.

Each code-concern finding goes to a verifier before any routing — the same
three-verdict standard the single-run gate applies, at this tick's Copilot step.
A verdict is conclusive only when an actual check ran: the verifier executes a
command against the flagged HEAD and captures its output. Reading the source
never produces a conclusive verdict. The verdict carries
`{ verdict, checkCommand, checkOutput, evidence }`; a conclusive verdict with an
empty `checkCommand` or `checkOutput` downgrades to inconclusive.

- **confirmed** — the check reproduces the defect. The finding joins the fix tick
  carrying its repro, and the fix re-runs that same check, adds a regression test
  where the suite covers the surface, lands in one commit, pushes, and replies on
  the thread with the fix SHA and the before/after output. No page.
- **refuted** — the check shows the code already behaves correctly in the exact
  scenario the finding claims is broken. The tick replies on the thread with the
  command and output, resolves it, and counts it clean. No page.
- **inconclusive** — everything else, and the verifier's default: no runnable
  check exists, the check is infeasible here, the results are ambiguous, or the
  fix needs a product decision. Any doubt sorts here.

On one or more inconclusive findings, do not auto-fix them and do not let the
tick mark the PR ready. Run the
[`copilot-finding-triage`](../copilot-finding-triage/SKILL.md) gate: send the
ntfy alert with the per-finding summary and evidence note and the Copilot review
link, then hold for the user's response on a 45-minute deadline that spans
ticks — carry the deadline in the run's persisted state so each tick reads it on
entry. Act on the user's direction when it arrives inside the window; when the
deadline passes with no response, run teardown and report the inconclusive
findings un-reviewed.

## Budget-aware tick boundaries

Before starting any tick, estimate whether the remaining session/usage
budget covers one full clean tick (worst case: a BUGBOT fetch + a
full-diff CODE_REVIEW + a fix commit + replies). If it does not, do not
start the tick. Stop at the current tick boundary: write updated state to
`$CLAUDE_JOB_DIR/pr-converge-state.json`, write the durable handoff (see
[State persistence](#state-persistence)), then report the exact resume
command (`/pr-converge <PR URL>`) and the persisted `phase`/`tick_count`.
A tick cut off mid-flight poisons the resume state — clean SHAs recorded
against work that never landed — so an unstarted tick is always cheaper
than a half-finished one.

## Findings discipline

Every finding, reply, and report states verified facts only — no hedging
language (`likely`, `probably`, `should`, `appears to`). Verify each
claim against the code on `current_head` before stating it; the
anti-hallucination Stop hook rejects hedged output, forcing a rework
pass. A claim that cannot be verified is reported as unverified, not
softened.

## State persistence

Single-PR mode persists loop state to `$CLAUDE_JOB_DIR/pr-converge-state.json`.
On tick entry, read this file if it exists to restore phase, tick_count, and
clean-at SHAs. On tick exit, write updated state before calling ScheduleWakeup
so the next tick resumes with accurate state.

After the state write and before ScheduleWakeup, write the durable handoff so a
fresh session in a new job can resume this run:

```
python "$HOME/.claude/skills/_shared/pr-loop/scripts/write_handoff.py" \
  --pr-number <N> --head-ref <branch> --phase <phase> \
  --resume-command "/pr-converge <PR URL>" \
  --state-file "$CLAUDE_JOB_DIR/pr-converge-state.json" \
  --completed-steps "<clean phases this run>"
```

It writes `handoff.json`, `HANDOFF.md`, and `state-copy.json` under
`~/.claude/runtime/pr-loop/<run-name>/`. The job-dir state stays the source of
truth for a resumed tick; the handoff copy is the pointer a fresh session reads
when `$CLAUDE_JOB_DIR` is gone.

Fields: `phase`, `tick_count`, `bugbot_clean_at`, `code_review_clean_at`,
`bugteam_clean_at`, `copilot_clean_at`, `current_head`,
`bugbot_acknowledged_at`, `bugbot_down`, `copilot_down`,
`bugteam_skill_invoked_at_head`, `bugteam_skill_invoked_at_tick`,
`agents_session_id`, `persistent_agents`.

## Persistent per-step agents

Three step-scoped agents persist across ticks so their context carries
forward: `fix_executor`, `thread_sweep`, and `copilot_watch`, recorded in
the `persistent_agents` map
([`reference/state-schema.md`](reference/state-schema.md)).

- **Resume:** read `persistent_agents.<key>`. When an entry exists,
  `SendMessage` to the stored `agent_id` with a tick payload that restates
  the PR scope, `current_head`, the PR worktree path, this tick's findings
  or threads, and the report-back contract. Bump `last_used_tick`, then
  await completion.
- **First spawn:** `Agent(subagent_type: "clean-coder", name:
  "prc-fix-<PR#>")` — the `name` makes the agent a persistent teammate
  that idles awaiting messages. Record `{agent_id, created_tick,
  last_used_tick}` under the step key. Keep the spawn prompt fix-shaped,
  never audit-shaped: the `pr_converge_bugteam_enforcer` hook blocks
  audit-shaped clean-coder spawns during the BUGTEAM phase.
- **Stale or dead id:** on a `SendMessage` failure, or no acknowledgment
  within one bounded wait, drop the map entry, spawn a fresh named agent,
  record it, and continue the tick. Never abort a tick on a stale id;
  never retry the same dead id.
- **Fresh every round (never persisted):** the Step 5 `/code-review high --fix`
  pass and the Step 6 bugteam audit (unbiased eyes each round; the
  enforcer needs the formal Skill call), and every `code-verifier` — a
  named code-verifier never fires `SubagentStop`, so no verdict mints (see
  the named-`code-verifier` entry in the Gotchas list below).
- **Shutdown:** at loop end (convergence or a stop condition), send each
  persistent agent a shutdown request and clear `persistent_agents` before
  the `pr-loop-lifecycle` Close.

## Gotchas

Highest-signal content. Append a bullet each time a tick fails in a new
way — these are the hard-won lessons that keep the loop honest. Once this
grows to 5 or more items, suggest spinning up a subagent to investigate, fix,
post a fresh PR in a fresh branch based on origin main to the user.

- **`ScheduleWakeup` not in subagent tool registries** — background
  `general-purpose` tick cannot schedule re-entry; only parent session
  with `ScheduleWakeup` in registry can call it.
- **`state.json` without §Concurrency lock loses merges** when teammates
  finish in same wall-clock window.
- **`tick_count` must not double-increment** — conversation state line
  only when **no** `state.json`; with `state.json`, only the
  orchestrator bump increments.
- **Bugbot trigger and detection** — CI check-run based. Full flow at
  [`per-tick.md` Step 3](reference/per-tick.md); see also
  `~/.claude/skills/pr-converge/scripts/check_bugbot_ci.py --help`.
- **Bot login fields differ by endpoint** — `get_reviews` returns
  `.user.login` (object), but `get_review_comments` returns `.author`
  (string, not an object). Always check the correct fields and use
  case-insensitive substring matching on login values, never strict
  equality.
- **`is_outdated` is informational, not a skip flag** — GitHub marks a
  thread `is_outdated=true` when the line it anchors to has changed since
  the comment was posted. The original concern can still apply to current
  code (the fix may have moved, not landed). The convergence gate counts
  every thread with `is_resolved == false` regardless of `is_outdated`.
  Outdated threads must be verified against current HEAD and either
  fix-and-resolved or just resolved (with an inline reply explaining why
  the concern no longer applies).
- **Tilde paths fail on Windows Git Bash** — `~/.claude/skills/...`
  resolves to the wrong home directory in Bash-tool contexts. Use
  `$HOME/.claude/skills/...` in shell invocations or `Path.home() /
  ".claude/skills/..."` in Python scripts. Script invocations through
  Bash that reference `~` produce "file not found" errors
  indistinguishable from actual script failures.
- **PowerShell cmdlets fail in Bash tool** — `.ps1` scripts and
  `pwsh` calls run through the PowerShell tool, not Bash. Bash on
  Windows is Git Bash which cannot execute PowerShell cmdlets. Route all
  PowerShell work through the PowerShell tool or `pwsh -NoProfile -File`.
- **Cross-repo PR: route cwd into the PR worktree before `/code-review`** —
  `/code-review high --fix` (Step 5) audits the repo of the current working
  directory. When the session is rooted in a different repo than the PR,
  `EnterWorktree` cannot re-root (it is scoped to the session's repo);
  resolve the PR worktree and `cd` into it per
  [Step 1.5](reference/per-tick.md). Skipping this reviews and edits the
  wrong repo. The route is routine and automatic — never a material fork
  to pause on.
- **A named/teammate `code-verifier` never mints a verdict** — In a background-job session, an `Agent`-tool `code-verifier` spawned with a `name` (or otherwise as a persistent teammate) goes idle/"available" awaiting messages rather than terminating, so its `SubagentStop` never fires. `verifier_verdict_minter.py` mints the verdict only on `SubagentStop`, so no verdict file is written and `verified_commit_gate` blocks the `git commit`/`git push` with "no passing verification verdict" even though the verifier emitted `all_pass`. A `shutdown_request` is ignored and `TaskStop` cannot resolve the teammate's id. Spawn the code-verifier as a one-shot agent with NO `name` (a plain async `Agent` call) so it runs to completion and fires `SubagentStop`, minting the verdict bound to the live surface. Keep the work tree frozen between verification and the commit so the minted surface hash still matches.

## Progress checklist

State variables (`phase`, `bugbot_clean_at`, `code_review_clean_at`,
`copilot_clean_at`, counters) are
defined in [`reference/state-schema.md`](reference/state-schema.md). Ground rules
in [`reference/ground-rules.md`](reference/ground-rules.md).

Each step references its spoke file for full procedural detail — MCP calls,
script invocations, decision criteria. Every "return to Step N" means the next
tick starts fresh from that step.

**Hard gate: do not advance from any step while ANY unresolved review
thread exists on the PR.** The sweep semantics and per-thread handling live
in the `pr-fix-protocol` skill's unresolved-thread sweep
(`../pr-fix-protocol/SKILL.md`).

**Full-PR-diff rule: every CODE-REVIEW round (Step 5) and every BUGTEAM
round (Step 6) covers the FULL `origin/main...HEAD` diff — every file
the PR touches.** A round that scopes to a subset — only the last commit,
only files touched since the prior clean SHA, only bugbot-flagged paths,
or any other delta cut — does not satisfy the gate, and a "clean" verdict
against a partial diff is not a valid clean. Re-run the round against the
full diff before recording `code_review_clean_at` or treating the bugteam
round as converged. This rule holds every tick, every loop, every PR.

- [ ] **Step 0: Open the run**
      Apply the `pr-loop-lifecycle` skill's Open section
      (`../pr-loop-lifecycle/SKILL.md`): permission grant + worktree preflight.

- [ ] **Step 1: Resolve PR scope + PR worktree**
      Apply the `pr-scope-resolve` skill (`../pr-scope-resolve/SKILL.md`)
      with caller `pr-converge`. Resolve the **PR
      worktree** — the local checkout every local step this tick targets:
      the `EnterWorktree` checkout when the PR shares the session's repo,
      else a checkout of the PR's repo that the working directory routes
      into via `cd`. Cross-repo routing is automatic, not a fork.
      See: [`reference/per-tick.md` § Step 1](reference/per-tick.md)
      and [§ Step 1.5](reference/per-tick.md)

- [ ] **Step 2: Initialize loop state**
      `phase = CODE_REVIEW`; all counters at zero; `run_name` resolved.

- [ ] **Step 3: Mergeability check**
      See: [`reference/convergence-gates.md` § (c)](reference/convergence-gates.md)

      ```
      pull_request_read(method="get") → .mergeable_state, .mergeable
      ```

      - [ ] mergeable → advance to Step 4
      - [ ] not mergeable → rebase → force-push → return to Step 1

- [ ] **Step 4: BUGBOT — terminal Bugbot confirmation gate**
      The terminal external gate. Step 6 routes here after BUGTEAM converges, so
      Bugbot confirms code the internal passes already drove to clean.
      See: [`reference/per-tick.md` § BUGBOT terminal gate + Step 3](reference/per-tick.md)

      - [ ] **Availability gate (runs first, every BUGBOT entry).**
            Gate semantics live in the `reviewer-gates` skill
            (`../reviewer-gates/SKILL.md` § Gate 1). Cursor Bugbot is off by default and runs only when `CLAUDE_REVIEWS_ENABLED` lists `bugbot`; a `bugbot` token in `CLAUDE_REVIEWS_DISABLED` keeps it off even then.
            `python "$HOME/.claude/_shared/pr-loop/scripts/reviews_disabled.py" --reviewer bugbot`
            - [ ] Exit 0 (Bugbot disabled for this run — the default) → set `bugbot_down = true`, advance to the Step 7 convergence gates (no trigger, no wait, no agent). Cursor Bugbot is skipped for the entire run.
            - [ ] Exit 1 → continue below.

      Fetch bugbot reviews + inline comments on `current_head`.

      - [ ] **dirty** (findings on `current_head`) →
            - [ ] Apply the `pr-fix-protocol` skill (`../pr-fix-protocol/SKILL.md`) to this tick's findings
            - [ ] Push → reset `bugbot_clean_at = null`, `code_review_clean_at = null` → `phase = CODE_REVIEW` → return to Step 5
      - [ ] **clean** (no findings on `current_head`) →
            - [ ] Count ALL unresolved threads on PR (`is_resolved == false`) → zero? advance; >0? fix + resolve first
            - [ ] `bugbot_clean_at = current_head`
            - [ ] Advance to the Step 7 convergence gates
      - [ ] **no review yet / commit_id mismatch** →
            Apply the `reviewer-gates` skill's Bugbot flow
            (`../reviewer-gates/SKILL.md` § Gate 3) against `current_head`,
            then map its outcomes:
            - [ ] Silent pass → `bugbot_clean_at = current_head` → advance to the Step 7 convergence gates
            - [ ] Already queued, or trigger acknowledged → schedule 360s wakeup → return to Step 4 next tick
            - [ ] Bugbot down → `bugbot_down = true` → advance to the Step 7 convergence gates (bypass)
- [ ] **Step 5: CODE-REVIEW — entry phase: static sweep, review, fix, advance**
      The first internal step of every convergence tick (Step 2 seeds
      `phase = CODE_REVIEW`), re-entered after any fix push.
      See: [`reference/per-tick.md` § CODE_REVIEW entry](reference/per-tick.md)

      Pre-condition: the working directory is the Step 1.5 PR worktree on
      `current_head` (`git rev-parse --show-toplevel` is that checkout).
      When the session is rooted in a different repo than the PR, `cd`
      into the PR worktree first — `/code-review` audits the repo of the
      current working directory, so this routing targets the real PR
      diff. This `cd` is routine and automatic.

      - [ ] **Static sweep — runs first, before `/code-review`.** Run the
            deterministic gates over the full `origin/main...HEAD` changed files:
            `python "$HOME/.claude/_shared/pr-loop/scripts/code_rules_gate.py" --base origin/main`,
            `ruff`, `mypy`, and stem-matched `pytest`.
            - [ ] Any failure → apply the `pr-fix-protocol` skill
                  (`../pr-fix-protocol/SKILL.md`), commit/push, reset
                  `bugbot_clean_at = null` and `code_review_clean_at = null`, stay
                  `phase = CODE_REVIEW`, and re-run (return to Step 5).
            - [ ] Clean → run `/code-review` below.

      Run Claude Code's built-in `/code-review high --fix` on the full
      `origin/main...HEAD` diff —
      the [local diff review](https://code.claude.com/docs/en/code-review#review-a-diff-locally)
      — so it reviews the diff and applies its findings to the working
      tree. Invoke `/code-review high --fix` so the pre-catch pass gets broad
      coverage regardless of the session's current effort.

      **Scope: the FULL `origin/main...HEAD` diff every tick** — every file
      the PR touches. Do not delta-scope to commits added since the prior
      clean SHA, do not scope to a single file, do not scope to bugbot's
      flagged paths. Before running, confirm the working tree is on the
      PR's HEAD with no uncommitted edits, then invoke `/code-review high --fix`
      with no path arguments so it audits the whole branch diff against
      `origin/main`. A partial-scope round does not count and cannot set
      `code_review_clean_at`.

      - [ ] **fixes applied** (working tree changed) →
            - [ ] Commit the applied fixes (one commit) → push
            - [ ] reset `bugbot_clean_at = null`, `code_review_clean_at = null`
            - [ ] stay `phase = CODE_REVIEW` → return to Step 5 (internal-first)
      - [ ] **clean** (no changes applied) →
            - [ ] Zero unresolved threads per the `pr-fix-protocol` sweep (`../pr-fix-protocol/SKILL.md`) → advance; else fix + resolve first (same skill)
            - [ ] `code_review_clean_at = current_head`
            - [ ] `phase = BUGTEAM` → advance to Step 6

- [ ] **Step 6: BUGTEAM — run, decide, fix, reply, resolve**
      See: [`reference/per-tick.md` § Step 2 BUGTEAM](reference/per-tick.md);
      [`../bugteam/SKILL.md`](../bugteam/SKILL.md)

      Pre-condition: `code_review_clean_at == current_head`.

      Step 6 advances ONLY after `Skill({skill: "bugteam", args: "<PR URL>"})`
      fires this tick. Substituting an `Agent({subagent_type: "clean-coder"})`
      audit call for the formal Skill invocation is a protocol violation — the
      `pr_converge_bugteam_enforcer` hook blocks it. `qbug` is NOT an accepted
      substitute; `bugteam` is the only allowed skill at this step.

      **Scope: the FULL `origin/main...HEAD` diff every tick** — every file
      the PR touches. Pass the PR URL as the sole argument so bugteam audits
      the whole branch diff against `origin/main`. Do not pass a file list,
      a path filter, a commit range, or any "just the new commits since
      last clean" cut — bugteam owns its own discovery on the full PR diff.
      A partial-scope round does not count and cannot satisfy the
      converged-on-current-HEAD condition below.

      After bugteam completes, re-resolve HEAD.

      - [ ] **bugteam pushed new commits** →
            - [ ] Verify all bugteam review threads replied + resolved
            - [ ] reset `bugbot_clean_at = null`, `code_review_clean_at = null`
            - [ ] `phase = CODE_REVIEW` → schedule 360s wakeup → return to Step 5
      - [ ] **converged (zero findings), no push** →
            - [ ] Count ALL unresolved threads on PR (`is_resolved == false`) → zero? advance; >0? fix + resolve first
            - [ ] `phase = BUGBOT` → advance to Step 4 (terminal Bugbot gate)
      - [ ] **findings without committed fixes** →
            - [ ] Apply the `pr-fix-protocol` skill (`../pr-fix-protocol/SKILL.md`) to the findings
            - [ ] Push → reset `bugbot_clean_at = null`, `code_review_clean_at = null` → `phase = CODE_REVIEW` → return to Step 5

- [ ] **Step 7: Convergence gates**
      Full procedure: [`reference/convergence-gates.md`](reference/convergence-gates.md).

      Pre-condition: Step 6 converged AND (`bugbot_clean_at == current_head` OR
      `bugbot_down`). The terminal Bugbot gate (Step 4) sets that state just
      before these gates run. Count unresolved threads before each gate.
      Every gate records evidence; gate (f) cites evidence from (a)–(e).

      - [ ] **(a) Copilot findings** — fetch Copilot on `current_head`; dirty → fix + return to Step 5; clean → stamp `copilot_clean_at`; absent → continue; when `copilot_down`, skip
      - [ ] **(b) Claude reviewer** — fetch Claude on `current_head`; dirty → fix + return to Step 5; clean or absent → continue
      - [ ] **(c) Mergeability** — `mergeable_state == "clean"` and `mergeable == true`; dirty → rebase + return to Step 1; blocked/behind/unknown/unstable → hard blocker
      - [ ] **(d) Post-convergence Copilot request** — request Copilot when not pending and not `copilot_down`; enter `COPILOT_WAIT` (Step 7a); when `copilot_down`, skip to (e)
      - [ ] **(e) Thread-resolution** — zero unresolved threads across the PR; else sweep + fix/resolve
      - [ ] **(f) Mark ready** — run `check_convergence.py`; exit 0 → `update_pull_request(draft=false)` → Step 8; exit 1 → fix path; exit 2 → retry/stop

- [ ] **Step 7a: COPILOT_WAIT — fetch Copilot, decide**
      See: [`reference/per-tick.md` § Step 2 COPILOT_WAIT](reference/per-tick.md)

      This step does not run when `copilot_down == true`: gate (d) skips the
      Copilot request, so the loop never enters COPILOT_WAIT.

      Fetch Copilot reviews + inline comments on `current_head`.

      - [ ] **clean (no findings)** →
            `copilot_clean_at = current_head` → return to Step 7 (re-validate gates (b), (c), then (e), (f))
      - [ ] **dirty (findings present)** →
            - [ ] Apply the `pr-fix-protocol` skill (`../pr-fix-protocol/SKILL.md`) to the findings
            - [ ] Push → reset markers → `phase = CODE_REVIEW` → return to Step 5
      - [ ] **no review yet** →
            increment `copilot_wait_count` → ≥ 3 = hard blocker → stop
            schedule 360s wakeup → return to Step 7a next tick

- [ ] **Step 8: Clean working tree**
      `pr-loop-lifecycle` Close (`../pr-loop-lifecycle/SKILL.md`).
      See: [`pr-loop-lifecycle/reference/teardown-publish-permissions.md` § Clean working tree](../pr-loop-lifecycle/reference/teardown-publish-permissions.md)

- [ ] **Step 9: Rewrite PR description**
      `pr-loop-lifecycle` Close.
      See: [`pr-loop-lifecycle/reference/teardown-publish-permissions.md` § Publish the final PR description](../pr-loop-lifecycle/reference/teardown-publish-permissions.md)

- [ ] **Step 10: Revoke project permissions (always)**
      `pr-loop-lifecycle` Close (`../pr-loop-lifecycle/SKILL.md` § Close).

- [ ] **Step 11: Print final report**
      Print this block verbatim — no paraphrase, no extra commentary:
      ```
      /pr-converge exit: converged
      Loops: <N>
      Final commit: <SHA>
      ```

## Edge cases

| Situation | Read |
|---|---|
| Multi-PR session (`state.json` exists) | [`reference/multi-pr-orchestration.md`](reference/multi-pr-orchestration.md) |
| Hard blocker or user stops loop | [`reference/stop-conditions.md`](reference/stop-conditions.md) |
| Tick is ambiguous against the steps above | [`reference/examples.md`](reference/examples.md) |

## Folder map

- `SKILL.md` — this hub.
- `reference/` — workflow detail per situation.
- `workflows/` — pacing implementations.
