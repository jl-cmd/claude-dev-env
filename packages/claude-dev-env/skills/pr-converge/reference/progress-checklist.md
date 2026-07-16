# pr-converge progress checklist

The per-tick step sequence for the pr-converge loop. The hub
([`../SKILL.md`](../SKILL.md)) points here; run these steps in order, one pass
per tick.

State variables (`phase`, `bugbot_clean_at`, `code_review_clean_at`,
`bugteam_clean_at`, `copilot_clean_at`, `merge_state_status`, counters) are
defined in [`state-schema.md`](state-schema.md). Ground rules
in [`ground-rules.md`](ground-rules.md).

Each step references its spoke file for full procedural detail — MCP calls,
script invocations, decision criteria. Every "return to Step N" means the next
tick starts fresh from that step.

**Hard gate: do not advance from any step while ANY unresolved review
thread exists on the PR.** Sweep semantics and per-thread handling live in
the shared fix protocol
([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md)
step 12; skill deltas in [`fix-protocol.md`](fix-protocol.md)).

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
      (`../../pr-loop-lifecycle/SKILL.md`): permission grant + worktree preflight.

- [ ] **Step 1: Resolve PR scope + PR worktree**
      Apply Step 1.5 scope resolution in
      [`per-tick.md`](per-tick.md). Resolve the **PR
      worktree** — the local checkout every local step this tick targets:
      the `EnterWorktree` checkout when the PR shares the session's repo,
      else a checkout of the PR's repo that the working directory routes
      into via `cd`. Cross-repo routing is automatic, not a fork.
      See: [`per-tick.md` § Step 1](per-tick.md)
      and [§ Step 1.5](per-tick.md)

- [ ] **Step 2: Initialize loop state**
      `phase = CODE_REVIEW`; all counters at zero; `run_name` resolved.

- [ ] **Step 3: Mergeability check**
      See: [`convergence-gates.md` § (c)](convergence-gates.md)

      ```
      pull_request_read(method="get") → .mergeable_state, .mergeable
      ```

      - [ ] mergeable → advance to Step 4
      - [ ] not mergeable → rebase → force-push → return to Step 1

- [ ] **Step 4: BUGBOT — terminal Bugbot confirmation gate**
      Step 6 routes here after BUGTEAM converges. Bugbot confirms code the
      internal passes already drove to clean.
      See: [`per-tick.md` § BUGBOT terminal gate + Step 3](per-tick.md);
      availability and trigger via `reviewer-gates`
      (`../../reviewer-gates/SKILL.md` § Gate 1 / Gate 3).

      - [ ] **disabled / down** → `bugbot_down = true` → Step 7
      - [ ] **dirty on `current_head`** → apply shared fix protocol
            ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md);
            skill deltas in [`fix-protocol.md`](fix-protocol.md))
            → push → reset push-invalidated markers → `phase = CODE_REVIEW` → Step 5
      - [ ] **clean on `current_head`** → zero unresolved threads (else fix + resolve first)
            → `bugbot_clean_at = current_head` → Step 7
      - [ ] **no review / commit_id mismatch** → `reviewer-gates` Bugbot flow (Gate 3):
            silent pass → stamp + Step 7; queued/triggered → 360s wakeup → Step 4;
            down → `bugbot_down = true` → Step 7

- [ ] **Step 5: CODE-REVIEW — static sweep, review, fix, advance**
      Entry phase every tick; re-entered after any fix push.
      See: [`per-tick.md` § CODE_REVIEW entry](per-tick.md).
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
      See: [`per-tick.md` § Step 2 BUGTEAM](per-tick.md);
      [`../../bugteam/SKILL.md`](../../bugteam/SKILL.md).
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
      Full procedure: [`convergence-gates.md`](convergence-gates.md).

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
      See: [`per-tick.md` § Step 2 COPILOT_WAIT](per-tick.md).
      Skipped entirely when `copilot_down` (gate (d) never enters this phase).

      - [ ] **clean** → `copilot_clean_at = current_head` → Step 7 (re-validate (b), (c), (e), (f))
      - [ ] **dirty** → apply shared fix protocol
            ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md);
            skill deltas in [`fix-protocol.md`](fix-protocol.md))
            → push → reset markers → `phase = CODE_REVIEW` → Step 5
      - [ ] **no review yet** → increment `copilot_wait_count` → ≥ 3 hard-blocks;
            else 360s wakeup → Step 7a next tick

- [ ] **Step 8: Clean working tree**
      `pr-loop-lifecycle` Close (`../../pr-loop-lifecycle/SKILL.md`).
      See: [`../../pr-loop-lifecycle/reference/teardown-publish-permissions.md` § Clean working tree](../../pr-loop-lifecycle/reference/teardown-publish-permissions.md)

- [ ] **Step 9: Rewrite PR description**
      `pr-loop-lifecycle` Close.
      See: [`../../pr-loop-lifecycle/reference/teardown-publish-permissions.md` § Publish the final PR description](../../pr-loop-lifecycle/reference/teardown-publish-permissions.md)

- [ ] **Step 10: Revoke project permissions (always)**
      `pr-loop-lifecycle` Close (`../../pr-loop-lifecycle/SKILL.md` § Close).

- [ ] **Step 11: Print final report**
      Print this block verbatim — no paraphrase, no extra commentary:
      ```
      /pr-converge exit: converged
      Loops: <N>
      Final commit: <SHA>
      ```
