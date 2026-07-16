---
name: pr-converge
description: >-
  Loops Cursor Bugbot, a code review, a bug audit, and Copilot on the current
  PR, applying TDD fixes until all are clean on one HEAD. Use when the user says
  '/pr-converge', 'drive PR to convergence', 'loop bugbot and bugteam', 'babysit
  bugbot and bugteam', 'until both are clean', or 'converge this PR'.
---

# PR Converge

A code-review ↔ bugteam ↔ Bugbot ↔ Copilot loop on a draft PR: the internal
code-review and bugteam passes drive the code to clean first, then Cursor
Bugbot and Copilot run as terminal confirmation gates, until all are clean on
the same `HEAD` and mergeable. On `pacer=schedule_wakeup`, one tick runs per
invocation and the next tick is scheduled. On `pacer=portable`, ticks run
continuously in-session (see
[`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md)).

## Transport check (before any GitHub step)

Run `command -v gh`; when it succeeds, run `gh auth status`; once the PR
scope is resolved, run `gh api repos/<owner>/<repo> --jq .permissions.push`
and take `true` as the pass. When any check fails, run the
`pr-loop-cloud-transport` skill first and route every `gh` operation in this
skill through its substitution matrix.

## Pre-flight

### Pacer selection

Scan the tool list for `ScheduleWakeup`. Record whether it is present, then
select the pacer:

```
python "$HOME/.claude/skills/_shared/pr-loop/scripts/select_converge_pacer.py" \
  --skill pr-converge \
  --has-workflow <0|1> \
  --has-schedule-wakeup <0|1>
```

- `pacer=schedule_wakeup` — native tick pacing via `ScheduleWakeup` (see
  [`workflows/schedule-wakeup-loop.md`](workflows/schedule-wakeup-loop.md)).
- `pacer=portable` — continuous in-session driver on
  [`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md).
  **Do not abort** because `ScheduleWakeup` is missing.

### Worktree isolation

When the tool list includes `EnterWorktree`, call it with no arguments before
any API call, file read, or edit. Agent-view sessions start in the shared
checkout; Bash (`gh`, `git`) does not auto-isolate. Do not proceed until the
working directory contains `.claude/worktrees/`. If `EnterWorktree` fails,
report the failure and stop.

When `EnterWorktree` is absent, isolate with git worktree machinery per
[`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md)
§ Isolation and worktree, then run strict
`preflight_worktree.py` for the PR's owner/repo. Fail closed only when the
checkout is not the PR's repo on the PR head ref.

`EnterWorktree` (or the portable worktree path) isolates the session repo.
When the PR lives in a different repo, Step 1.5 routes the working directory
into a **PR worktree** of that repo on its head branch (routine, never a
pause). See [`reference/per-tick.md` § Step 1.5](reference/per-tick.md).

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

Tier, verify, and route each Copilot finding via
[`copilot-finding-triage`](../copilot-finding-triage/SKILL.md) (self-healing
auto-fix; code-concern verify then confirmed / refuted / inconclusive).

**pr-converge phase routing after triage:**

- Self-healing and **confirmed** findings join the fix tick on `current_head`;
  after push, reset clean-at SHAs, set `phase = CODE_REVIEW`, return to Step 5.
- **Refuted** findings resolve clean on the thread; no phase change.
- One or more **inconclusive** findings: do not mark ready. Run the triage
  skill's user gate (ntfy + 45-minute hold across ticks; persist the deadline so
  each tick reads it on entry). Act on the user's direction inside the window;
  on timeout, teardown and report the findings un-reviewed.
- Enter `COPILOT_WAIT` only from gate (d) after requesting a Copilot review
  (Step 7 → 7a). Stay on `COPILOT_WAIT` until a review surfaces at
  `current_head`, `copilot_wait_count >= 3` hard-blocks, or `copilot_down`
  skips the Copilot path entirely.

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
clean-at SHAs. On tick exit, write updated state before the next pacer step
(`ScheduleWakeup` when `pacer=schedule_wakeup`; continuous continue or
in-session poll when `pacer=portable`) so the next tick resumes with accurate
state.

After the state write and before the next pacer step, write the durable handoff
so a fresh session in a new job can resume this run:

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
`bugteam_clean_at`, `copilot_clean_at`, `merge_state_status`, `current_head`,
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
- **Fresh every round (never persisted):** the Step 5 host-aware
  `invoke_code_review.py` / `/code-review high --fix` pass and the Step 6
  bugteam audit (unbiased eyes each round; the enforcer needs the formal
  Skill call), and every `code-verifier` — a named code-verifier never fires
  `SubagentStop`, so no verdict mints (see the named-`code-verifier` entry
  in the Gotchas list below).
- **Shutdown:** at loop end (convergence or a stop condition), send each
  persistent agent a shutdown request and clear `persistent_agents` before
  the `pr-loop-lifecycle` Close.

## Gotchas

Highest-signal content. Append a bullet each time a tick fails in a new
way — these are the hard-won lessons that keep the loop honest. Once this
grows to 5 or more items, suggest spinning up a subagent to investigate, fix,
post a fresh PR in a fresh branch based on origin main to the user.

- **`ScheduleWakeup` not in subagent tool registries** — background
  `general-purpose` tick cannot schedule re-entry; only the parent session
  with `ScheduleWakeup` (or the portable continuous driver on the parent)
  may pace the next tick.
- **Portable host has no durable wake outside the session** — when
  `pacer=portable`, budget and context bound how many ticks complete; write
  handoff at a tick boundary and resume with `/pr-converge <PR URL>`.
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
- **`isOutdated` has dual scope** — GitHub marks a thread `isOutdated=true`
  when the line it anchors to has changed since the comment was posted. The
  machine gate (`check_convergence.py` / [convergence-gates.md](reference/convergence-gates.md)
  gate (e)) excludes `isOutdated == true` bot threads from the fail count —
  only non-outdated unresolved bot threads fail the gate. The agent-side
  unresolved-thread sweep in the shared fix protocol
  ([`../../_shared/pr-loop/fix-protocol.md`](../../_shared/pr-loop/fix-protocol.md)
  step 12; skill deltas in [`reference/fix-protocol.md`](reference/fix-protocol.md))
  still verifies outdated unresolved threads against HEAD before resolve when
  the protocol requires it (the original concern can still apply when the fix
  moved rather than landed).
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
- **Cross-repo PR: route cwd into the PR worktree before Step 5 review** —
  `invoke_code_review.py` and `/code-review high --fix` audit the repo of the
  cwd (the helper's `--cwd`). When the session is rooted in a different repo
  than the PR, `EnterWorktree` cannot re-root (it is scoped to the session's
  repo); resolve the PR worktree and `cd` into it per
  [Step 1.5](reference/per-tick.md). Skipping this reviews and edits the
  wrong repo. The route is routine and automatic — never a material fork
  to pause on.
- **A named/teammate `code-verifier` never mints a verdict** — In a background-job session, an `Agent`-tool `code-verifier` spawned with a `name` (or otherwise as a persistent teammate) goes idle/"available" awaiting messages rather than terminating, so its `SubagentStop` never fires. `verifier_verdict_minter.py` mints the verdict only on `SubagentStop`, so no verdict file is written and `verified_commit_gate` blocks the `git commit`/`git push` with "no passing verification verdict" even though the verifier emitted `all_pass`. A `shutdown_request` is ignored and `TaskStop` cannot resolve the teammate's id. Spawn the code-verifier as a one-shot agent with NO `name` (a plain async `Agent` call) so it runs to completion and fires `SubagentStop`, minting the verdict bound to the live surface. Keep the work tree frozen between verification and the commit so the minted surface hash still matches.

## Progress checklist

State variables (`phase`, `bugbot_clean_at`, `code_review_clean_at`,
`bugteam_clean_at`, `copilot_clean_at`, `merge_state_status`, counters) are
defined in [`reference/state-schema.md`](reference/state-schema.md). Ground rules
in [`reference/ground-rules.md`](reference/ground-rules.md).

Each step references its spoke file for full procedural detail — MCP calls,
script invocations, decision criteria. Every "return to Step N" means the next
tick starts fresh from that step.

**Hard gate: do not advance from any step while ANY unresolved review
thread exists on the PR.** Sweep semantics and per-thread handling live in
the shared fix protocol
([`../../_shared/pr-loop/fix-protocol.md`](../../_shared/pr-loop/fix-protocol.md)
step 12; skill deltas in [`reference/fix-protocol.md`](reference/fix-protocol.md)).

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
      Apply Step 1.5 scope resolution in
      [`reference/per-tick.md`](reference/per-tick.md). Resolve the **PR
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
      Step 6 routes here after BUGTEAM converges. Bugbot confirms code the
      internal passes already drove to clean.
      See: [`reference/per-tick.md` § BUGBOT terminal gate + Step 3](reference/per-tick.md);
      availability and trigger via `reviewer-gates`
      (`../reviewer-gates/SKILL.md` § Gate 1 / Gate 3).

      - [ ] **disabled / down** → `bugbot_down = true` → Step 7
      - [ ] **dirty on `current_head`** → apply shared fix protocol
            ([`../../_shared/pr-loop/fix-protocol.md`](../../_shared/pr-loop/fix-protocol.md);
            skill deltas in [`reference/fix-protocol.md`](reference/fix-protocol.md))
            → push → reset push-invalidated markers → `phase = CODE_REVIEW` → Step 5
      - [ ] **clean on `current_head`** → zero unresolved threads (else fix + resolve first)
            → `bugbot_clean_at = current_head` → Step 7
      - [ ] **no review / commit_id mismatch** → `reviewer-gates` Bugbot flow (Gate 3):
            silent pass → stamp + Step 7; queued/triggered → 360s wakeup → Step 4;
            down → `bugbot_down = true` → Step 7

- [ ] **Step 5: CODE-REVIEW — static sweep, review, fix, advance**
      Entry phase every tick; re-entered after any fix push.
      See: [`reference/per-tick.md` § CODE_REVIEW entry](reference/per-tick.md).
      Pre-condition: cwd is the Step 1.5 PR worktree on `current_head`.
      Scope: FULL `origin/main...HEAD` diff every tick (no path args, no delta cut).
      Review always runs at effort high on model opus through
      `invoke_code_review.py`. Mode decision inputs: host profile + session
      model. Call:
      `python "$HOME/.claude/scripts/invoke_code_review.py" --cwd <PR-worktree>
      --session-model <alias>`. Chain mode uses that cwd and empty stdin; the
      chain process never commits and never pushes. JSON stdout carries
      `mode` (`in_session` | `chain`), `served_command`, `returncode`, and
      `dirty_tree`. Config/host errors still emit that JSON with non-zero
      `returncode` (no traceback-only failure).

      - [ ] **Static sweep fails** → apply shared fix protocol → push → reset markers
            → stay CODE_REVIEW → Step 5
      - [ ] **`mode == in_session`** (Claude host, session model opus) → run
            `/code-review high --fix` in-session (no path args)
      - [ ] **`mode == chain`** (any other host or non-opus session) → helper
            already ran the headless review; read `returncode`,
            `served_command`, and `dirty_tree` from JSON
      - [ ] **failed review** (`returncode != 0`, or chain with null
            `served_command`) → do not set `code_review_clean_at` → stay
            CODE_REVIEW → Step 5
      - [ ] **fixes applied** (`dirty_tree` true / working tree dirty) →
            commit + push via shared fix protocol → reset markers → stay
            CODE_REVIEW → Step 5
      - [ ] **clean** (successful serve: `returncode == 0`, chain
            `served_command` non-null when chain, and `dirty_tree` false) →
            zero unresolved threads (else fix + resolve) →
            `code_review_clean_at = current_head` → `phase = BUGTEAM` → Step 6

- [ ] **Step 6: BUGTEAM — run, decide, fix, reply, resolve**
      See: [`reference/per-tick.md` § Step 2 BUGTEAM](reference/per-tick.md);
      [`../bugteam/SKILL.md`](../bugteam/SKILL.md).
      Pre-condition: `code_review_clean_at == current_head`.
      Mandatory: `Skill({skill: "bugteam", args: "<PR URL>"})` this tick
      (enforcer-blocked otherwise; `qbug` is not a substitute). Scope: FULL
      `origin/main...HEAD` diff. Re-resolve HEAD after bugteam.

      - [ ] **bugteam pushed** → verify threads replied + resolved → reset markers
            → `phase = CODE_REVIEW` → 360s wakeup → Step 5
      - [ ] **converged, no push** → zero unresolved threads →
            `bugteam_clean_at = current_head` → `phase = BUGBOT` → Step 4
      - [ ] **findings without committed fixes** → apply shared fix protocol → push →
            reset markers → `phase = CODE_REVIEW` → Step 5

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
      See: [`reference/per-tick.md` § Step 2 COPILOT_WAIT](reference/per-tick.md).
      Skipped entirely when `copilot_down` (gate (d) never enters this phase).

      - [ ] **clean** → `copilot_clean_at = current_head` → Step 7 (re-validate (b), (c), (e), (f))
      - [ ] **dirty** → apply shared fix protocol
            ([`../../_shared/pr-loop/fix-protocol.md`](../../_shared/pr-loop/fix-protocol.md);
            skill deltas in [`reference/fix-protocol.md`](reference/fix-protocol.md))
            → push → reset markers → `phase = CODE_REVIEW` → Step 5
      - [ ] **no review yet** → increment `copilot_wait_count` → ≥ 3 hard-blocks;
            else 360s wakeup → Step 7a next tick

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

## Depends on / invokes

| Skill / path | Role |
|---|---|
| `pr-loop-lifecycle` | Open (permission grant + worktree preflight) and Close (cleanup, PR description, revoke) |
| `reviewer-gates` | Copilot quota gate, Bugbot availability, Bugbot trigger flow |
| `copilot-finding-triage` | Tier, verify, and route each Copilot finding |
| `bugteam` | Full-diff bug audit in Step 6 (Skill invocation mandatory) |
| `pr-loop-cloud-transport` | When `gh` is unavailable or unauthenticated |
| [`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md) | Continuous in-session pacer when `ScheduleWakeup` is absent |
| [`../../_shared/pr-loop/fix-protocol.md`](../../_shared/pr-loop/fix-protocol.md) | Shared 13-step fix sequence (TDD, commit, push, reply, resolve) |
| [`reference/fix-protocol.md`](reference/fix-protocol.md) | pr-converge deltas on the shared fix protocol |

## Package file index

| Path | Purpose |
|---|---|
| `SKILL.md` | Hub: pre-flight, state, progress checklist, gotchas |
| `CLAUDE.md` | Package map for agents working in this skill |
| `pr_converge_skill_constants/` | Importable constants for skill scripts |
| `reference/per-tick.md` | Full per-tick procedure (phases, cwd routing, pacing) |
| `reference/convergence-gates.md` | Six gates before mark-ready |
| `reference/fix-protocol.md` | pr-converge fix-protocol deltas |
| `reference/ground-rules.md` | Non-negotiable loop constraints |
| `reference/state-schema.md` | `pr-converge-state.json` fields |
| `reference/stop-conditions.md` | Hard stops without convergence |
| `reference/multi-pr-orchestration.md` | Multi-PR session orchestration |
| `reference/examples.md` | Worked tick sequences |
| `reference/obstacles/` | Per-obstacle fix runbooks |
| `scripts/` | Convergence helpers, Copilot fetch, fix-reply poster, tests |
| `workflows/schedule-wakeup-loop.md` | ScheduleWakeup pacing (`pacer=schedule_wakeup`) |
| [`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md) | Portable continuous pacer (`pacer=portable`) |
