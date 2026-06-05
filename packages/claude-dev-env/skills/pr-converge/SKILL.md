---
name: pr-converge
description: >-
  Drives the current PR to convergence by looping Cursor Bugbot, a
  code-review pass, a second-opinion bug audit, and Copilot — applying
  TDD fixes, posting inline replies, and re-triggering reviewers each
  tick until all reviewers are clean on the same HEAD. Use when the user
  says
  '/pr-converge', 'drive PR to convergence', 'loop bugbot and bugteam',
  'babysit bugbot and bugteam', 'until both are clean', or 'converge this
  PR'.
---

# PR Converge

One tick per invocation. Bugbot ↔ code-review ↔ bugteam ↔ Copilot loop on
a draft PR until all are clean on the same `HEAD` and mergeable.

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

## State persistence

Single-PR mode persists loop state to `$CLAUDE_JOB_DIR/pr-converge-state.json`.
On tick entry, read this file if it exists to restore phase, tick_count, and
clean-at SHAs. On tick exit, write updated state before calling ScheduleWakeup
so the next tick resumes with accurate state.

Fields: `phase`, `tick_count`, `bugbot_clean_at`, `code_review_clean_at`,
`bugteam_clean_at`, `copilot_clean_at`, `current_head`,
`bugbot_acknowledged_at`, `bugbot_down`, `bugteam_skill_invoked_at_head`,
`bugteam_skill_invoked_at_tick`.

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

## Progress checklist

State variables (`phase`, `bugbot_clean_at`, `code_review_clean_at`,
`copilot_clean_at`, counters) are
defined in [`reference/state-schema.md`](reference/state-schema.md). Ground rules
in [`reference/ground-rules.md`](reference/ground-rules.md).

Each step references its spoke file for full procedural detail — MCP calls,
script invocations, decision criteria. Every "return to Step N" means the next
tick starts fresh from that step.

**Hard gate: do not advance from any step while ANY unresolved review
thread exists on the PR.** The thread-count filter is purely
`is_resolved == false` — author, commit anchor, and `is_outdated` are
all irrelevant. After every fix, reply to each finding comment and
resolve the thread via `pull_request_review_write(method="resolve_thread")`.
For each unresolved thread, verify the concern against current HEAD;
either fix-and-resolve, or reply-with-note-and-resolve when the concern
no longer applies.

**Full-PR-diff rule: every CODE-REVIEW round (Step 5) and every BUGTEAM
round (Step 6) covers the FULL `origin/main...HEAD` diff — every file
the PR touches.** A round that scopes to a subset — only the last commit,
only files touched since the prior clean SHA, only bugbot-flagged paths,
or any other delta cut — does not satisfy the gate, and a "clean" verdict
against a partial diff is not a valid clean. Re-run the round against the
full diff before recording `code_review_clean_at` or treating the bugteam
round as converged. This rule holds every tick, every loop, every PR.

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

      - [ ] **Opt-out gate (runs first, every BUGBOT entry).**
            `python "$HOME/.claude/_shared/pr-loop/scripts/reviews_disabled.py" --reviewer bugbot`
            - [ ] Exit 0 (`CLAUDE_REVIEWS_DISABLED` lists `bugbot`) → set `bugbot_down = true`, `phase = CODE_REVIEW`, advance to Step 5 (bypass). Cursor Bugbot is skipped for the entire run.
            - [ ] Exit 1 → continue below.

      Fetch bugbot reviews + inline comments on `current_head`.

      - [ ] **dirty** (findings on `current_head`) →
            - [ ] Fix each finding (spawn `clean-coder`)
            - [ ] Reply to each finding comment via `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py`
            - [ ] Resolve each addressed thread via `pull_request_review_write(method="resolve_thread")`
            - [ ] Push → return to Step 4
      - [ ] **clean** (no findings on `current_head`) →
            - [ ] Count ALL unresolved threads on PR (`is_resolved == false`) → zero? advance; >0? fix + resolve first
            - [ ] `bugbot_clean_at = current_head`
            - [ ] `phase = CODE_REVIEW`
            - [ ] Advance to Step 5
      - [ ] **no review yet / commit_id mismatch** →
            - [ ] Run `python ~/.claude/skills/pr-converge/scripts/check_bugbot_ci.py --owner <O> --repo <R> --check-clean --sha <current_head>`
            - [ ] Exit 0 (bugbot CI completed with success/neutral conclusion and no review = silent pass) → `bugbot_clean_at = current_head` → `phase = CODE_REVIEW` → advance to Step 5
            - [ ] Exit 1 (not a silent pass) or Exit 2 (gh CLI error — silent pass not confirmable) → Run `python ~/.claude/skills/pr-converge/scripts/check_bugbot_ci.py --owner <O> --repo <R> --check-active --sha <current_head>`
            - [ ] Exit 0 (already queued) → schedule 360s wakeup → return to Step 4 next tick
            - [ ] Exit 1 → post exactly `bugbot run` via `add_issue_comment` (no `@cursor[bot]` mention, no other text), wait 8s
            - [ ] Run `python ~/.claude/skills/pr-converge/scripts/check_bugbot_ci.py --owner <O> --repo <R> --sha <current_head>`
            - [ ] Exit non-zero → `bugbot_down = true` → `phase = CODE_REVIEW` → advance to Step 5 (bypass)
            - [ ] Exit 0 → record `bugbot_acknowledged_at`, schedule 360s wakeup → return to Step 4
- [ ] **Step 5: CODE-REVIEW — run, fix, reset, advance**
      See: [`reference/per-tick.md` § Step 2 CODE_REVIEW](reference/per-tick.md)

      Pre-condition: `bugbot_clean_at == current_head` (or `bugbot_down == true`).

      Run Claude Code's built-in `/code-review --fix` on the full
      `origin/main...HEAD` diff —
      the [local diff review](https://code.claude.com/docs/en/code-review#review-a-diff-locally)
      — so it reviews the diff and applies its findings to the working
      tree. Pass no effort argument, so the review uses the session's
      current effort.

      **Scope: the FULL `origin/main...HEAD` diff every tick** — every file
      the PR touches. Do not delta-scope to commits added since the prior
      clean SHA, do not scope to a single file, do not scope to bugbot's
      flagged paths. Before running, confirm the working tree is on the
      PR's HEAD with no uncommitted edits, then invoke `/code-review --fix`
      with no path arguments so it audits the whole branch diff against
      `origin/main`. A partial-scope round does not count and cannot set
      `code_review_clean_at`.

      - [ ] **fixes applied** (working tree changed) →
            - [ ] Commit the applied fixes (one commit) → push
            - [ ] reset `bugbot_clean_at = null`, `code_review_clean_at = null`
            - [ ] Re-trigger bugbot (Step 4 "no review yet" checklist)
            - [ ] `phase = BUGBOT` → schedule 360s wakeup → return to Step 4
      - [ ] **clean** (no changes applied) →
            - [ ] Count ALL unresolved threads on PR (`is_resolved == false`) → zero? advance; >0? fix + resolve first
            - [ ] `code_review_clean_at = current_head`
            - [ ] `phase = BUGTEAM` → advance to Step 6

- [ ] **Step 6: BUGTEAM — run, decide, fix, reply, resolve**
      See: [`reference/per-tick.md` § Step 2 BUGTEAM](reference/per-tick.md);
      [`../../bugteam/SKILL.md`](../../bugteam/SKILL.md)

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
            - [ ] Re-trigger bugbot (Step 4 "no review yet" checklist)
            - [ ] `phase = BUGBOT` → schedule 360s wakeup → return to Step 4
      - [ ] **converged (zero findings) + `bugbot_clean_at == current_head`** →
            - [ ] Count ALL unresolved threads on PR (`is_resolved == false`) → zero? advance; >0? fix + resolve first
            - [ ] Advance to Step 7
      - [ ] **converged + `bugbot_clean_at ≠ current_head`** →
            `phase = BUGBOT` → schedule 360s wakeup → return to Step 4
      - [ ] **findings without committed fixes** →
            - [ ] Fix each finding (spawn `clean-coder`)
            - [ ] Reply to each finding comment via `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py`
            - [ ] Resolve each addressed thread via `pull_request_review_write(method="resolve_thread")`
            - [ ] Push → `phase = BUGBOT` → return to Step 4

- [ ] **Step 7: Convergence gates**
      See: [`reference/convergence-gates.md`](reference/convergence-gates.md)

      Pre-condition: Step 6 converged AND `bugbot_clean_at == current_head`.
      Count unresolved threads before each gate.

      **(a) Universal unresolved-thread sweep**
      - [ ] Fetch ALL unresolved threads on the PR:
            ```
            pull_request_read(method="get_review_comments")
              → filter threads where is_resolved == false
            ```
      - [ ] Any unresolved? → For each: verify concern against current HEAD;
            if still applies → Fix (spawn `clean-coder`) → reply → resolve;
            if no longer applies → reply-with-note → resolve. Push if any code changed → return to Step 4
      - [ ] Fetch Copilot review on `current_head` (top-level review state — uses get_reviews, identifies by reviewer):
            ```
            python ~/.claude/skills/pr-converge/scripts/fetch_copilot_reviews.py --owner <O> --repo <R> --pr-number <N>
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
      - [ ] `phase = COPILOT_WAIT` → schedule 360s wakeup → return to Step 7a next tick

      **(d) Thread resolution — author-agnostic, outdated-agnostic**
      ```
      pull_request_read(method="get_review_comments")
        → count threads where is_resolved == false
      ```
      - [ ] zero unresolved → gate (e)
      - [ ] unresolved → For each: verify against HEAD;
            still applies → Fix (spawn `clean-coder`) → reply → resolve;
            no longer applies → reply-with-note → resolve.
            Push if code changed → return to Step 4

      **(e) Mark ready**
      - [ ] Run automated convergence check:
            ```
            python $HOME/.claude/skills/pr-converge/scripts/check_convergence.py \
              --owner <O> --repo <R> --pr-number <N>
            ```
      - [ ] Exit 0 (all pass) → `update_pull_request(draft=false)` → advance to Step 8
      - [ ] Exit 1 (FAIL lines) → address each failure → return to Step 4
      - [ ] Exit 2 (gh error) → retry once; persistent → stop

- [ ] **Step 7a: COPILOT_WAIT — fetch Copilot, decide**
      See: [`reference/per-tick.md` § Step 2 COPILOT_WAIT](reference/per-tick.md)

      Fetch Copilot reviews + inline comments on `current_head`.

      - [ ] **clean (no findings)** →
            `copilot_clean_at = current_head` → return to Step 7 (re-validate gates b, d, e)
      - [ ] **dirty (findings present)** →
            - [ ] Fix each finding (spawn `clean-coder`)
            - [ ] Reply to each finding comment via `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py`
            - [ ] Resolve each addressed thread via `pull_request_review_write(method="resolve_thread")`
            - [ ] Push → `phase = BUGBOT` → return to Step 4
      - [ ] **no review yet** →
            increment `copilot_wait_count` → ≥ 3 = hard blocker → stop
            schedule 360s wakeup → return to Step 7a next tick

- [ ] **Step 8: Clean working tree**
      See: [`bugteam/reference/teardown-publish-permissions.md` § Step 4](../../bugteam/reference/teardown-publish-permissions.md)

- [ ] **Step 9: Rewrite PR description**
      See: [`bugteam/reference/teardown-publish-permissions.md` § Step 4.5](../../bugteam/reference/teardown-publish-permissions.md)

- [ ] **Step 10: Revoke project permissions**
      `python "$HOME/.claude/skills/bugteam/scripts/revoke_project_claude_permissions.py"`

- [ ] **Step 11: Print final report**
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
