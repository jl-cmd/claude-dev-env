---
name: pr-converge
description: >-
  Drives the current PR to convergence by looping Cursor Bugbot, a
  second-opinion bug audit, and Copilot — applying TDD fixes, posting
  inline replies, and re-triggering reviewers each tick until all three
  reviewers are clean on the same HEAD. Use when the user says
  '/pr-converge', 'drive PR to convergence', 'loop bugbot and bugteam',
  'babysit bugbot and bugteam', 'until both are clean', or 'converge this
  PR'.
---

# PR Converge

One tick per invocation. Bugbot ↔ bugteam ↔ Copilot loop on a draft PR
until all three are clean on the same `HEAD` and mergeable.

## Pre-flight

Pause and physically scan the tool list at the top of this conversation
for the literal string `ScheduleWakeup`. If you see it, proceed. If the
string is absent after scanning, report `pr-converge requires
ScheduleWakeup; aborting` and stop.

If the current working directory path does not contain `.claude/worktrees/`,
call `EnterWorktree` with no arguments. This isolates the convergence loop
from the user's working copy so parallel jobs and manual edits cannot
interleave. If `EnterWorktree` fails (not a git repo, or already in a
worktree), continue in place.

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
  (string, not an object). Threads use `is_outdated` (not `commit_id`) to
  indicate staleness. Always check the correct fields and use
  case-insensitive substring matching on login values, never strict
  equality.

## Progress checklist

State variables (`phase`, `bugbot_clean_at`, `copilot_clean_at`, counters) are
defined in [`reference/state-schema.md`](reference/state-schema.md). Ground rules
in [`reference/ground-rules.md`](reference/ground-rules.md).

Each step references its spoke file for full procedural detail — MCP calls,
script invocations, decision criteria. Every "return to Step N" means the next
tick starts fresh from that step.

**Hard gate: do not advance from any step while unresolved bot review threads
exist on `current_head`.** After every fix, reply to each finding comment and
resolve the thread. Count unresolved threads before advancing.

- [ ] **Step 0: Grant project permissions**
      `python "$HOME/.claude/skills/bugteam/scripts/grant_project_claude_permissions.py"`

- [ ] **Step 1: Resolve PR scope**
      Capture owner, repo, number, head SHA, branch.
      See: [`reference/per-tick.md` § Step 1](reference/per-tick.md)

- [ ] **Step 2: Initialize loop state**
      `phase = BUGBOT`; all counters at zero; `run_name` resolved.

- [ ] **Step 3: Mergeability check**
      See: [`reference/convergence-gates.md` § (c)](reference/convergence-gates.md)

      ```
      pull_request_read(method="get") → .mergeable_state, .mergeable
      ```

      - [ ] mergeable → advance to Step 4
      - [ ] not mergeable → rebase → force-push → return to Step 1

- [ ] **Step 4: BUGBOT — fetch, decide, fix, reply, resolve**
      See: [`reference/per-tick.md` § Step 2 BUGBOT + Step 3](reference/per-tick.md)

      Fetch bugbot reviews + inline comments on `current_head`.

      - [ ] **dirty** (findings on `current_head`) →
            - [ ] Fix each finding (spawn `clean-coder`)
            - [ ] Reply to each finding comment via `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py`
            - [ ] Resolve each addressed thread via `pull_request_review_write(method="resolve_thread")`
            - [ ] Push → return to Step 4
      - [ ] **clean** (no findings on `current_head`) →
            - [ ] Count unresolved bugbot threads → zero? advance; >0? fix + resolve first
            - [ ] `bugbot_clean_at = current_head`
            - [ ] Advance to Step 5
      - [ ] **no review yet / commit_id mismatch** →
            - [ ] Run `python ~/.claude/skills/pr-converge/scripts/check_bugbot_ci.py --owner <O> --repo <R> --check-active --sha <current_head>`
            - [ ] Exit 0 (already queued) → schedule 360s wakeup → return to Step 4 next tick
            - [ ] Exit 1 → post exactly `bugbot run` via `add_issue_comment` (no `@cursor[bot]` mention, no other text), wait 8s
            - [ ] Run `python ~/.claude/skills/pr-converge/scripts/check_bugbot_ci.py --owner <O> --repo <R> --sha <current_head>`
            - [ ] Exit non-zero → `bugbot_down = true` → advance to Step 5 (bypass)
            - [ ] Exit 0 → record `bugbot_acknowledged_at`, schedule 360s wakeup → return to Step 4
- [ ] **Step 5: BUGTEAM — run, decide, fix, reply, resolve**
      See: [`reference/per-tick.md` § Step 2 BUGTEAM](reference/per-tick.md);
      [`../../bugteam/SKILL.md`](../../bugteam/SKILL.md)

      Pre-condition: `bugbot_clean_at == current_head` (or `bugbot_down == true`).

      Run `Skill({skill: "bugteam", args: "<PR URL>"})`.
      After bugteam completes, re-resolve HEAD.

      - [ ] **bugteam pushed new commits** →
            - [ ] Verify all bugteam review threads replied + resolved
            - [ ] Re-trigger bugbot (Step 4 "no review yet" checklist)
            - [ ] `phase = BUGBOT` → schedule 360s wakeup → return to Step 4
      - [ ] **converged (zero findings) + `bugbot_clean_at == current_head`** →
            - [ ] Count unresolved threads (all bot reviewers) → zero? advance; >0? fix + resolve first
            - [ ] Advance to Step 6
      - [ ] **converged + `bugbot_clean_at ≠ current_head`** →
            `phase = BUGBOT` → schedule 360s wakeup → return to Step 4
      - [ ] **findings without committed fixes** →
            - [ ] Fix each finding (spawn `clean-coder`)
            - [ ] Reply to each finding comment via `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py`
            - [ ] Resolve each addressed thread via `pull_request_review_write(method="resolve_thread")`
            - [ ] Push → `phase = BUGBOT` → return to Step 4

- [ ] **Step 6: Convergence gates**
      See: [`reference/convergence-gates.md`](reference/convergence-gates.md)

      Pre-condition: Step 5 converged AND `bugbot_clean_at == current_head`.
      Count unresolved threads before each gate.

      **(a) Copilot findings**
      - [ ] Fetch ALL unresolved Copilot threads across the PR (any commit):
            ```
            pull_request_read(method="get_review_comments") → filter copilot
              → unresolved (is_outdated=false, is_resolved=false)
            ```
      - [ ] Any unresolved? → Fix (spawn `clean-coder`) → reply → resolve → push → return to Step 4
      - [ ] Fetch Copilot review on `current_head`:
            ```
            python ~/.claude/skills/pr-converge/scripts/fetch_copilot_reviews.py --owner <O> --repo <R> --pr-number <N>
            ```
            Then fetch inline comments via MCP:
            ```
            pull_request_read(method="get_review_comments") → filter copilot
              → unresolved (is_outdated=false, is_resolved=false)
              → anchored to latest Copilot review on current_head
            ```
      - [ ] dirty → Fix (spawn `clean-coder`) → reply → resolve threads → push → return to Step 4
      - [ ] clean (no findings) → `copilot_clean_at = current_head` → gate (b)
      - [ ] no review yet → gate (b)

      **(b) Mergeability re-check**
      ```
      pull_request_read(method="get") → .mergeable_state, .mergeable
      ```
      - [ ] mergeable → gate (c)
      - [ ] not mergeable → rebase → push → return to Step 1

      **(c) Request Copilot review**
      - [ ] Check for pending Copilot review:
            ```
            python ~/.claude/skills/pr-converge/scripts/check_pending_reviews.py --owner <O> --repo <R> --pr-number <N>
              → filter by copilot user
            ```
      - [ ] Pending review already exists → skip request → gate (d)
      - [ ] No pending review → request:
            ```
            gh api --method POST repos/<O>/<R>/pulls/<N>/requested_reviewers \
              -f 'reviewers[]=copilot-pull-request-reviewer[bot]'
            ```
      - [ ] `phase = COPILOT_WAIT` → schedule 360s wakeup → return to Step 6a next tick

      **(d) Thread resolution**
      ```
      pull_request_read(method="get_review_comments") → filter bot reviewers
        → count unresolved (is_outdated=false, is_resolved=false)
      ```
      - [ ] zero unresolved → gate (e)
      - [ ] unresolved → Fix (spawn `clean-coder`) → reply → resolve → push → return to Step 4

      **(e) Mark ready**
      - [ ] Verify all pre-conditions ([`convergence-gates.md` § f](reference/convergence-gates.md))
      - [ ] `update_pull_request(draft=false)`
      - [ ] Advance to Step 7

- [ ] **Step 6a: COPILOT_WAIT — fetch Copilot, decide**
      See: [`reference/per-tick.md` § Step 2 COPILOT_WAIT](reference/per-tick.md)

      Fetch Copilot reviews + inline comments on `current_head`.

      - [ ] **clean (no findings)** →
            `copilot_clean_at = current_head` → return to Step 6 (re-validate gates b, d, e)
      - [ ] **dirty (findings present)** →
            - [ ] Fix each finding (spawn `clean-coder`)
            - [ ] Reply to each finding comment via `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py`
            - [ ] Resolve each addressed thread via `pull_request_review_write(method="resolve_thread")`
            - [ ] Push → `phase = BUGBOT` → return to Step 4
      - [ ] **no review yet** →
            increment `copilot_wait_count` → ≥ 3 = hard blocker → stop
            schedule 360s wakeup → return to Step 6a next tick

- [ ] **Step 7: Clean working tree**
      See: [`bugteam/reference/teardown-publish-permissions.md` § Step 4](../../bugteam/reference/teardown-publish-permissions.md)

- [ ] **Step 8: Rewrite PR description**
      See: [`bugteam/reference/teardown-publish-permissions.md` § Step 4.5](../../bugteam/reference/teardown-publish-permissions.md)

- [ ] **Step 9: Revoke project permissions**
      `python "$HOME/.claude/skills/bugteam/scripts/revoke_project_claude_permissions.py"`

- [ ] **Step 10: Print final report**
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
