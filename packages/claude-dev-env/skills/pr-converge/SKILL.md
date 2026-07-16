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
edit. Agent-view sessions start in the shared checkout; Bash (`gh`, `git`)
does not auto-isolate. Do not proceed until the working directory contains
`.claude/worktrees/`. If `EnterWorktree` fails, report the failure and stop.

`EnterWorktree` isolates the session repo. When the PR lives in a different
repo, Step 1.5 routes the working directory into a **PR worktree** of that
repo on its head branch (routine, never a pause). See
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

Run the eleven-step per-tick sequence in
[`reference/progress-checklist.md`](reference/progress-checklist.md): Step 0
(open the run) through Step 11 (final report), each step pointing to its spoke
file for MCP calls, script invocations, and decision criteria. State variables
live in [`reference/state-schema.md`](reference/state-schema.md); ground rules in
[`reference/ground-rules.md`](reference/ground-rules.md).

Two hard gates bind every step:

- **No unresolved threads.** Do not advance from any step while any unresolved
  review thread exists on the PR (sweep semantics in the shared fix protocol,
  [`../../_shared/pr-loop/fix-protocol.md`](../../_shared/pr-loop/fix-protocol.md)
  step 12).
- **Full-PR-diff.** Every CODE-REVIEW (Step 5) and BUGTEAM (Step 6) round covers
  the full `origin/main...HEAD` diff — a "clean" verdict against a partial diff
  is not a valid clean.

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
| [`../../_shared/pr-loop/fix-protocol.md`](../../_shared/pr-loop/fix-protocol.md) | Shared 13-step fix sequence (TDD, commit, push, reply, resolve) |
| [`reference/fix-protocol.md`](reference/fix-protocol.md) | pr-converge deltas on the shared fix protocol |

## Package file index

| Path | Purpose |
|---|---|
| `SKILL.md` | Hub: pre-flight, state, progress checklist, gotchas |
| `CLAUDE.md` | Package map for agents working in this skill |
| `pr_converge_skill_constants/` | Importable constants for skill scripts |
| `reference/progress-checklist.md` | Per-tick eleven-step checklist (Step 0 open → Step 11 report) |
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
| `workflows/schedule-wakeup-loop.md` | ScheduleWakeup pacing |
