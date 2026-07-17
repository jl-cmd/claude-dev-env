# Per-tick work

## Contents

- [Invocation modes](#invocation-modes)
- [Pacing workflow](#pacing-workflow)
- [Step 1: Resolve current HEAD and PR context](#step-1-resolve-current-head-and-pr-context)
- [Step 1.5: Resolve the PR worktree (cwd routing)](#step-15-resolve-the-pr-worktree-cwd-routing)
- [Step 2: Branch on phase](#step-2-branch-on-phase)
- [Step 3: Re-trigger bugbot](#step-3-re-trigger-bugbot)
- [Step 4: Loop pacing](#step-4-loop-pacing)
- [Bugteam execution](#bugteam-execution)

Use on **draft PR**. Cursor Bugbot and `/bugteam` re-run after each push. Fix
findings between rounds until back-to-back clean on same `HEAD`, then mark
PR ready for review.

Run every tick in the parent harness session. Pacing depends on the selected
pacer from pre-flight (`select_converge_pacer.py`):

- `schedule_wakeup` — [`../workflows/schedule-wakeup-loop.md`](../workflows/schedule-wakeup-loop.md)
- `portable` — [`../../_shared/pr-loop/portable-driver.md`](../../_shared/pr-loop/portable-driver.md)

See [Pacing workflow](#pacing-workflow).

Every BUGTEAM tick runs **bugteam** — never hand-rolled substitute. Fix
protocol per [fix-protocol.md](fix-protocol.md). Pacing stays in the main
session (native `ScheduleWakeup` or the portable continuous driver).

## Invocation modes

- **`/pr-converge` with `pacer=schedule_wakeup`** runs one tick, then Step 4
  schedules the next via `ScheduleWakeup`. Omit the next wakeup only on
  convergence or **Stop conditions**.
- **`/pr-converge` with `pacer=portable`** runs ticks continuously in-session
  (poll waits at the same delays); write handoff at budget boundaries. See
  the portable driver.

## Pacing workflow

When `pacer=schedule_wakeup`, read
[`../workflows/schedule-wakeup-loop.md`](../workflows/schedule-wakeup-loop.md)
(installed copy under `$HOME/.claude/skills/pr-converge/workflows/`) before
Step 4. When `pacer=portable`, read
[`../../_shared/pr-loop/portable-driver.md`](../../_shared/pr-loop/portable-driver.md)
and skip `ScheduleWakeup` calls.

- **`/pr-converge`** (default): loops until convergence. After each tick
  (unless converged or stopped), run **Step 4** using the selected pacer.

## Step 1: Resolve current HEAD and PR context

Read prior tick's state line from most recent assistant message (or
initialize fields if none). Increment `tick_count` by 1 in conversation
state line when **no** `state.json` (single-PR only). With `state.json`, do
**not** increment here — orchestrator's per-tick bump is sole increment.

```bash
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get") → `.head.sha`
```

If owner/repo/number are not yet known, extract them from the PR URL.
If `current_head` changed since last tick, reset push-invalidated markers
per [ground-rules.md](ground-rules.md) / [state-schema.md](state-schema.md)
(all `*_clean_at`, `merge_state_status`, `bugbot_down`, `bugbot_acknowledged_at`,
`codex_down`) — new HEAD invalidates prior clean and down-detection state.

Capture `number`, `head.sha` (= `current_head`), owner/repo, branch.

## Step 1.5: Resolve the PR worktree (cwd routing)

The **PR worktree** is the local working tree of the PR's repo on its head
branch. Every local operation this tick runs there: the CODE_REVIEW static sweep
and `/code-review xhigh --fix`, every `clean-coder` fix spawn, and every commit and
push. `/code-review` and `git` both act on the repo of the current working
directory, so the working directory must be the PR worktree before any local
work begins. Re-resolve it every tick — a rebase or a fresh HEAD can move the
branch tip.

Classify the working directory against the PR's repo. The preflight script
reads the current working tree's origin, parses its `<owner>/<repo>` (accepting
the `https://github.com/<owner>/<repo>`, `git@github.com:<owner>/<repo>`, and
`ssh://git@github.com/<owner>/<repo>` forms and dropping any trailing `.git`),
and prints a `PREFLIGHT_OUTCOME=<same_repo|different_repo|re_rooted>` line plus a
human-readable summary:

```bash
python "$HOME/.claude/skills/_shared/pr-loop/scripts/preflight_worktree.py" --owner <owner> --repo <repo> --mode classify
```

A `same_repo` outcome exits 0 only when the worktree machinery is healthy; a
`same_repo` outcome whose `git worktree list` probe failed exits non-zero in
every mode. A `different_repo` outcome exits 0 in classify mode. A `re_rooted`
outcome (no git work tree, or no readable origin) exits non-zero. Route on the
`PREFLIGHT_OUTCOME` value:

- **`PREFLIGHT_OUTCOME=same_repo`** (the working directory is a checkout of the
  PR's repo): the `EnterWorktree`
  pre-flight checkout is the PR worktree, and the working directory already
  points here, so no `cd` is needed. Bring the branch to the PR head with the
  same deterministic `checkout -B` the cross-repo case uses, after confirming
  the tree carries no uncommitted edits — a non-empty `git status --porcelain`
  means a prior tick left a fix mid-flight, so escalate as a hard blocker:
  ```bash
  git fetch origin
  git checkout -B <branch> origin/<branch>
  ```
  When the script prints an `ABORT:` line whose recovery names `git worktree
  prune`, the working tree's worktree machinery is broken and the preflight
  exits non-zero: stop the tick, run that `git worktree prune` in the named
  directory, and re-run rather than continuing the checkout.

- **`PREFLIGHT_OUTCOME=different_repo`** (the session is rooted in another repo
  — for example, the PR lives in `llm-settings` while the session runs from
  `claude-dev-env`): route the working directory into a checkout of the
  PR's repo. This is routine and automatic — never pause, and never raise it as
  a fork (see [ground-rules.md](ground-rules.md)). `EnterWorktree` is scoped to
  the session's own repo and cannot re-root into the PR's repo.

  `<run_temp_dir>` is pr-converge's own `pr-converge-pr-<N>` directory under the
  system temp directory — named apart from bugteam's `bugteam-pr-<N>` run dir so
  the two never share a checkout when Step 6 runs bugteam on the same PR.
  pr-converge fills this path by hand; it does not route through the shared
  `_path_resolver` that bugteam uses. Reuse its `checkout` across ticks; create
  it once when it is absent. A fresh clone honors the global `core.hooksPath`, so git-side
  CODE_RULES enforcement covers the fix commit.

  1. Clone the PR branch when the checkout is absent:
     ```bash
     gh repo clone <owner>/<repo> "<run_temp_dir>/checkout" -- --branch <branch>
     ```
  2. Bring it to the PR head. On a reused checkout, confirm it carries no
     uncommitted edits first — a non-empty `git -C "<run_temp_dir>/checkout"
     status --porcelain` means a prior tick left a fix mid-flight, so escalate
     as a hard blocker rather than discard it. On a clean tree:
     ```bash
     git -C "<run_temp_dir>/checkout" fetch origin
     git -C "<run_temp_dir>/checkout" checkout -B <branch> origin/<branch>
     ```
  3. Change into it in a standalone Bash call so the working directory persists
     into the `/code-review` invocation that follows:
     ```bash
     cd "<run_temp_dir>/checkout"
     ```
  4. Confirm the route took before any local work:
     ```bash
     git rev-parse --show-toplevel
     git rev-parse HEAD
     ```
     The top level reads `<run_temp_dir>/checkout` and HEAD equals
     `current_head`.

  Spawn every `clean-coder` fix worker with the PR worktree path in its prompt
  so its edits land in the PR's repo — the same worktree-path handoff bugteam
  gives its fix worker. The
  GitHub API steps (BUGBOT fetch, convergence gates) and the bugteam Skill
  invocation are URL-driven and need no local checkout.

  Capture the session worktree path (the `EnterWorktree` checkout) before
  routing away. Step 0 grant, Step 8 working-tree cleanup, and Step 10 revoke
  read the current working directory and target the session repo, so `cd` back
  to the session worktree before Step 8 and remove `<run_temp_dir>` there with
  a Windows-safe recursive remove (per
  `$HOME/.claude/rules/windows-filesystem-safe.md`).

- **`PREFLIGHT_OUTCOME=re_rooted`** (the working directory is not a git work
  tree, or its origin remote is unreadable — a resumed or background session can
  re-root to the home directory): the tick cannot locate the PR's repo from
  here, so neither cwd reuse nor a temp-clone route is safe. Report the printed
  `ABORT` line as a hard blocker and stop the tick. Recover by starting the
  session from a checkout of the PR's repo and re-running.

## Step 2: Branch on `phase`

The internal passes drive the code to clean first. CODE_REVIEW is the entry phase
each tick; BUGTEAM follows; the terminal Bugbot gate confirms; then the
convergence gates and the terminal Copilot gate run. Every fix push re-enters at
CODE_REVIEW.

### `phase == CODE_REVIEW`

The entry phase of every convergence tick, re-entered after any fix push. It runs
a deterministic static sweep, then the thorough built-in review owned by the
**claude-review** skill
([`../../claude-review/SKILL.md`](../../claude-review/SKILL.md)):
`/code-review xhigh --fix` on model opus over the full `origin/main...HEAD` diff
via host-aware `invoke_code_review.py`. `/code-review` produces no GitHub review
artifact, so there are no code-review threads to resolve.

a. **Static sweep — runs first, before `/code-review`.** Run the deterministic
   gates over the full `origin/main...HEAD` changed files:
   `python "$HOME/.claude/_shared/pr-loop/scripts/code_rules_gate.py" --base origin/main`,
   `ruff`, `mypy`, and stem-matched `pytest`. On any failure, apply the
   shared fix protocol ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md); skill deltas in [`fix-protocol.md`](fix-protocol.md)), commit and push,
   reset push-invalidated markers per [ground-rules.md](ground-rules.md) /
   [state-schema.md](state-schema.md) (all `*_clean_at`, `merge_state_status`,
   `bugbot_down`, `bugbot_acknowledged_at`, `codex_down`), stay
   `phase = CODE_REVIEW`, and re-run the sweep. When the sweep is clean, run
   the host-aware review below.

b. Run **claude-review** for the built-in review procedure (prefer
   `Skill({skill: "claude-review", ...})`; when `Skill` is not invokable, read
   [`../../claude-review/SKILL.md`](../../claude-review/SKILL.md)). Full-diff rule,
   invoker JSON shape, and clean-stamp contract:
   [`../../claude-review/reference/full-diff-and-clean-stamp.md`](../../claude-review/reference/full-diff-and-clean-stamp.md).

   Before running, confirm the working directory is the PR worktree resolved
   in [Step 1.5](#step-15-resolve-the-pr-worktree-cwd-routing) — `git rev-parse
   --show-toplevel` is that checkout and `git rev-parse HEAD` equals
   `current_head` — with no uncommitted edits. When the session is rooted in a
   different repo than the PR, the `cd` from Step 1.5 supplies this; the
   persisted working directory is the cwd the review audits.

   Route every CODE_REVIEW pass through the host-aware helper
   `invoke_code_review.py`. Mode decision inputs are the host profile (detected
   by the helper) and the caller's session model short alias:

   ```bash
   python "$HOME/.claude/scripts/invoke_code_review.py" \
     --cwd "$(git rev-parse --show-toplevel)" \
     --session-model <session-model-alias>
   ```

   The helper prints one JSON object on stdout only:
   `{mode, served_command, returncode, dirty_tree}`. Chain mode sets cwd to the
   PR worktree and redirects stdin from the empty stream so the spawn does not
   wait for interactive input. The chain process never commits and never pushes
   — commit and push belong to this step via the shared fix protocol. On
   `ChainConfigurationError` or host `ValueError`, the helper still prints that
   JSON shape (non-zero `returncode`, null `served_command`) and exits non-zero
   — never a traceback-only failure.

   Match the first mode whose predicate holds:

   - **`mode == "in_session"`** (Claude host and session model is opus): run
     `/code-review xhigh --fix` with OPUS in this session with no path arguments so it
     audits the whole branch diff against `origin/main`. After it returns, a
     non-empty `git status --porcelain` means fixes applied (`dirty_tree`
     equivalent). Treat a failed in-session slash command the same as a failed
     review: do not set `code_review_clean_at`.
   - **`mode == "chain"`** (any other host, or a Claude session on any model
     other than opus): the helper already ran the headless review
     (`claude -p "/code-review xhigh --fix" --model opus` through the chain
     runner) with cwd set to the PR worktree. Read `returncode`,
     `served_command`, and `dirty_tree` from the JSON. A successful serve is
     `returncode == 0` with a non-null `served_command`. `dirty_tree` true
     means fixes applied; `dirty_tree` false is clean only after a successful
     serve.

   Do not delta-scope to commits added since the prior clean SHA, do not scope
   to a single file, do not scope to bugbot's flagged paths. A partial-scope
   round does not count and cannot set `code_review_clean_at`.

c. Decide (three branches; match first whose predicate holds):

   - **Failed review (`returncode != 0`, or chain mode with null
     `served_command`):** The review did not complete a successful serve. Do
     not set `code_review_clean_at`. Stay `phase = CODE_REVIEW`, apply Step 4 pacer
     (ScheduleWakeup or portable continue/poll), return. A failed chain often leaves `dirty_tree` false — that is
     not a clean stamp.
   - **Fixes applied (working tree dirty / `dirty_tree` true):** Commit the
     applied fixes in one commit → push, following the shared fix protocol
     commit and push steps ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md)). Reset
     push-invalidated markers per [ground-rules.md](ground-rules.md) /
     [state-schema.md](state-schema.md) (all `*_clean_at`, `merge_state_status`,
     `bugbot_down`, `bugbot_acknowledged_at`, `codex_down`). Stay
     `phase = CODE_REVIEW`, apply Step 4 pacer (ScheduleWakeup or portable continue/poll), return. Every fix push
     re-enters the internal passes on the new HEAD.
   - **Clean (successful serve: `returncode == 0`, chain `served_command`
     non-null when `mode == chain`, and `dirty_tree` false):** Set
     `code_review_clean_at = current_head`, `phase = BUGTEAM`. Continue
     BUGTEAM in same tick — back-to-back convergence requires code-review and
     bugteam clean on the same HEAD before the terminal gates run. Helper
     contract: `is_code_review_clean_stamp_allowed` is true only for this
     branch.

### `phase == BUGTEAM`

a. Run **bugteam** on current PR.

   Pass the PR URL as the sole argument so bugteam audits the FULL
   `origin/main...HEAD` diff — every file the PR touches. Bugteam owns
   its own discovery on the full PR diff. Do not pass a file list, a
   path filter, a commit range, or any "just the new commits since last
   clean" cut. A partial-scope round does not count and cannot satisfy
   the converged-on-current-HEAD condition in step (d).

   - **`Skill` invokable**: invoke bugteam
     with `Skill`.

     ```
Skill({skill: "bugteam", args:
"https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"})
     ```

   - **`Skill` not invokable** (typical delegated teammate): worker executes
     bugteam by reading [`../../bugteam/SKILL.md`](../../bugteam/SKILL.md). Same
     loop and gates; only harness steps differ.

b. **Re-resolve current HEAD (MANDATORY — never skip).** Bugteam may have
pushed commits during its run. `current_head` from Step 1 is stale:

   ```
   pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get") → `.head.sha`
   ```

   Capture `new_head`. Then check the most recent commit timestamp:

   ```
   list_commits(owner=OWNER, repo=REPO, sha="<branch>")
     → sort by `.commit.committer.date` descending → index 0 `.commit.committer.date`
   ```

   If the most recent commit timestamp is **less than 60 seconds ago**, the
   GitHub API may not have propagated it to review endpoints yet. Do not
   proceed with convergence-gates — schedule a 90s wakeup and return.
   Re-resolve HEAD next tick.

   If `new_head != current_head`, set `current_head = new_head` and reset
   push-invalidated markers per [ground-rules.md](ground-rules.md) /
   [state-schema.md](state-schema.md) (all `*_clean_at`, `merge_state_status`,
   `bugbot_down`, `bugbot_acknowledged_at`, `codex_down`). New commits
   invalidate prior clean and down-detection state.

c. Inspect bugteam outcome. Reports `convergence (zero findings)` or list
of unfixed findings with file:line.

d. Decide based on post-bugteam state — order matters. Check
pushed-during-bugteam FIRST so a convergence report against a stale HEAD
never falsely terminates:
   - **Audit pushed this tick (clean-at fields reset in step b):**
     `phase = CODE_REVIEW`, apply Step 4 pacer (ScheduleWakeup or portable continue/poll), return. Every fix push
     re-enters the internal passes on the new HEAD.
   - **Convergence AND no push:** the internal passes are clean on
     `current_head`. Stamp `bugteam_clean_at = current_head`, then
     `phase = BUGBOT` — route into the terminal Bugbot gate, which confirms
     and then runs the convergence gates. Continue BUGBOT in the same tick.
   - **Findings without committed fixes:** apply the shared fix protocol
     ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md); skill deltas in [fix-protocol.md](fix-protocol.md)). Reset push-invalidated markers
     per [ground-rules.md](ground-rules.md) / [state-schema.md](state-schema.md)
     (all `*_clean_at`, `merge_state_status`, `bugbot_down`,
     `bugbot_acknowledged_at`, `codex_down`), `phase = CODE_REVIEW`, apply Step 4 pacer
     (ScheduleWakeup or portable continue/poll), return.

### `phase == BUGBOT` (terminal gate)

The terminal external confirmation gate. BUGTEAM routes here once the internal
passes are clean; Bugbot confirms the HEAD, then the convergence gates run.

**Availability gate (runs first, before any fetch or trigger).**
`python "$HOME/.claude/_shared/pr-loop/scripts/reviews_disabled.py" --reviewer bugbot`

- Exit 0 (Bugbot disabled for this run — the default, unless
  `CLAUDE_REVIEWS_ENABLED` lists `bugbot`) → set `bugbot_down = true`, run the
  [Codex review step](#codex-review-step-conditional), advance to the
  [convergence gates](convergence-gates.md) in the same tick with the Bugbot
  gate bypassed; skip steps a–c below.
- Exit 1 (`CLAUDE_REVIEWS_ENABLED` lists `bugbot` and `CLAUDE_REVIEWS_DISABLED`
  does not) → go to step a.

Because `bugbot_down` resets on every push, this gate re-runs on every
BUGBOT entry. Cursor Bugbot is off by default and runs only when
`CLAUDE_REVIEWS_ENABLED` lists `bugbot`; a `bugbot` token in
`CLAUDE_REVIEWS_DISABLED` keeps it off even then.

a. Fetch Cursor Bugbot reviews newest-first, walk back until first clean:

   ```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_reviews")
   → filter `.user.login` for cursor/bugbot, sort by `.submitted_at` descending
   ```

   Track dirty entries (review body has `BUGBOT_REVIEW` markers with finding content); Fix protocol reads them back later this tick.

   Iterate from index 0 (most recent) toward older:

   - Dirty review → append JSON line with `{review_id, commit_id,
     submitted_at, body}`.
   - Stop at first clean. Older reviews presumed addressed at that
     checkpoint.
   - Index 0 clean → `$dirty_reviews_path` stays empty.

Capture `commit_id`, `submitted_at`, body, `classification` of index-0
review for decisions below. When branch routes to **Fix protocol**, address
**every** entry in `$dirty_reviews_path` — not just index 0.

b. Fetch ALL unresolved inline comment threads on the PR:

   ```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_review_comments")
   → filter threads where `is_resolved == false`
   ```

   Per-thread handling lives in the shared fix protocol's
   unresolved-thread sweep (`../../../_shared/pr-loop/fix-protocol.md`).

c. Decide (four branches; match first whose predicate holds):
   - **No bugbot review yet, OR latest review's `commit_id` ≠
     `current_head`:** Re-trigger bugbot (Step 3), set `bugbot_clean_at =
     null`, reset `inline_lag_streak = 0`, apply Step 4 pacer (ScheduleWakeup or portable continue/poll), return to the
     Bugbot gate next tick.
   - **`commit_id == current_head` AND zero unaddressed inline AND review
     body clean:** Set `bugbot_clean_at = current_head`, reset
     `inline_lag_streak = 0`, run the [Codex review step](#codex-review-step-conditional)
     then advance to the [convergence gates](convergence-gates.md) in the same
     tick.
   - **`commit_id == current_head` with unaddressed inline findings:**
     Apply the shared fix protocol ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md); skill deltas in [`fix-protocol.md`](fix-protocol.md)).
     Reset `inline_lag_streak = 0` and push-invalidated markers per
     [ground-rules.md](ground-rules.md) / [state-schema.md](state-schema.md)
     (all `*_clean_at`, `merge_state_status`, `bugbot_down`,
     `bugbot_acknowledged_at`, `codex_down`), `phase = CODE_REVIEW`. With
     `state.json`: the clean-coder teammate executes the fix, writes
     `state.json`, goes idle; the next tick re-enters CODE_REVIEW on the new
     HEAD. No `state.json` (single-PR): the lead executes it, stays
     `phase = CODE_REVIEW`. Apply Step 4 pacer (ScheduleWakeup or portable continue/poll), return.

### `phase == COPILOT_WAIT`

Post-convergence Copilot re-check. Enters after the convergence gates request a
Copilot review. Do **not** run bugteam here — the internal code-review and
bugteam passes already converged before this terminal gate.

a. Fetch latest Copilot review at `current_head` plus unaddressed inline
   comments:

   ```
python ~/.claude/skills/pr-converge/scripts/fetch_copilot_reviews.py --owner <O> --repo <R> --pr-number <N>
  → filter by `.commit_id == current_head`, sort by `.submitted_at` descending

python ~/.claude/skills/pr-converge/scripts/fetch_copilot_inline_comments.py --owner <O> --repo <R> --pr-number <N> --commit <current_head>
  → unaddressed inline threads on the latest Copilot review at current_head
   ```

b. Decide (three branches; match first whose predicate holds):

   - **Copilot review `state: APPROVED` at `current_head`:** Set
     `copilot_clean_at = current_head`. Record "Copilot APPROVED". Stay on
     `COPILOT_WAIT` — do not re-enter BUGTEAM. Continue to
     convergence-gates.md gate (b) in same tick; re-validate gates (b), (c),
     then (e), (f) on the same HEAD.
   - **Copilot review dirty (CHANGES_REQUESTED or COMMENTED with findings)
     at `current_head`:** Apply the shared fix protocol ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md); skill deltas in [`fix-protocol.md`](fix-protocol.md)) — it covers body-only findings with
     no inline threads. Reset push-invalidated markers per
     [ground-rules.md](ground-rules.md) / [state-schema.md](state-schema.md)
     (all `*_clean_at`, `merge_state_status`, `bugbot_down`,
     `bugbot_acknowledged_at`, `codex_down`). **Set `phase = CODE_REVIEW`**
     (NOT COPILOT_WAIT) — every fix push re-enters the internal passes on the
     new HEAD. Apply Step 4 pacer (ScheduleWakeup or portable continue/poll), return.
   - **No Copilot review at `current_head` yet:** Increment
     `copilot_wait_count` (init 0 on COPILOT_WAIT entry; reset to 0 on
     every push and on every successful Copilot review). `>= 3` → hard
     blocker per [stop-conditions.md](stop-conditions.md). Otherwise
     apply Step 4 pacer (ScheduleWakeup or portable continue/poll; 360s wait), return.

**Non-negotiable:** After any Copilot fix push, `phase` MUST route to
`CODE_REVIEW`. Never cycle COPILOT_WAIT → fix → COPILOT_WAIT. The
back-to-back-clean guarantee (the internal code-review and bugteam passes both
clean on the same HEAD before the terminal gates re-open) only holds when every
fix commit re-enters through CODE_REVIEW.

## Codex review step (conditional)

Run once the terminal Bugbot gate has confirmed HEAD (or set `bugbot_down`) and
**before** the [convergence gates](convergence-gates.md) machine checklist.
Uses the `codex-review` skill wrapper against the PR **base** branch (HEAD vs
base), never an invented commit range.

1. **Opt-out / down gate.**
   `python "$HOME/.claude/_shared/pr-loop/scripts/reviews_disabled.py" --reviewer codex`
   - Exit 0 → set `codex_down = true`, skip the skill, continue to convergence
     gates (export `CLAUDE_REVIEWS_DISABLED` including `codex` before the
     checklist so `check_convergence.py` bypasses without flags).
   - Exit 1 → continue.

2. **Usage probe.**
   `python "$HOME/.claude/skills/codex-review/scripts/codex_usage_probe.py"`
   - When `percent_left` is null or not strictly above the probe threshold
     constant (`WEEKLY_USAGE_GATE_THRESHOLD_PERCENT`): skip Codex; do not set
     `codex_clean_at`; continue to convergence gates (the machine checklist
     skips the condition on the same rule).
   - When above threshold: continue to the skill.

3. **Skill wrapper (HEAD vs base).** Invoke `codex-review` (or read
   `../../codex-review/SKILL.md` when `Skill` is not invokable) so the wrapper
   reviews the diff against the PR base branch at `current_head`.

4. **Classify.**
   - `clean` → set `codex_clean_at = current_head`; write the stamp into
     `$CLAUDE_JOB_DIR/pr-converge-state.json` (and pass `--codex-clean-at` into
     `check_convergence.py` when invoking the checklist).
   - `findings` → apply the shared fix protocol; reset push-invalidated markers
     (all `*_clean_at`, `merge_state_status`, `bugbot_down`,
     `bugbot_acknowledged_at`, `codex_down`); `phase = CODE_REVIEW`; schedule
     next wakeup; return.
   - `down` / `codex_down` → set `codex_down = true`; continue to convergence
     gates without blocking ready.

## Step 3: Re-trigger bugbot

- [ ] **Availability gate.** Enforced at BUGBOT entry (see `### phase == BUGBOT`).
  When Bugbot is disabled for the run — the default unless
  `CLAUDE_REVIEWS_ENABLED` lists `bugbot`, and always when
  `CLAUDE_REVIEWS_DISABLED` lists `bugbot` — the entry gate sets
  `bugbot_down = true` and advances to the convergence gates before any trigger
  flow runs, so the flow below is skipped.
- [ ] Apply the `reviewer-gates` skill's Bugbot flow
  (`../../reviewer-gates/SKILL.md` § Gate 3) against `current_head` — the
  silent-pass pre-check, the already-queued check, the trigger comment, and
  the acknowledge check, with their rationale. Map its outcomes:
- [ ] Silent pass → set `bugbot_clean_at = current_head`, run the
  [Codex review step](#codex-review-step-conditional), advance to the
  [convergence gates](convergence-gates.md) same tick
- [ ] Already queued → skip posting, wait for completion, advance to Step 4
- [ ] Trigger acknowledged (`bugbot_acknowledged_at` recorded) → advance to Step 4
- [ ] Bugbot down → set `bugbot_down = true`, run the
  [Codex review step](#codex-review-step-conditional), advance to the
  [convergence gates](convergence-gates.md) same tick

## Step 4: Loop pacing

Apply the pacer selected at pre-flight ([Pacing workflow](#pacing-workflow)).

### `pacer=schedule_wakeup`

**`ScheduleWakeup` field hints:**

- `delaySeconds: 360` after bugbot re-trigger. Exception:
  BUGBOT inline-lag branch uses `delaySeconds: 90` (no re-trigger;
  awaiting GitHub inline API).
- `reason`: short sentence on what is awaited, including `phase` and
  `bugbot_clean_at` SHA.
- `prompt: "/pr-converge"`.

**On convergence:** apply **Convergence** section of
`../workflows/schedule-wakeup-loop.md` (omit wakeups).

### `pacer=portable`

Do **not** call `ScheduleWakeup`. After writing state and handoff:

- **Immediate work next** → continue the next tick in the same turn.
- **Wait next** (Bugbot queued, COPILOT_WAIT with no review yet) → poll
  in-session for the same delay (`360` default, `90` on Bugbot inline-lag),
  then resume the same step. Honor the same hard caps as the ScheduleWakeup
  path.
- **Budget too low for a full tick** → stop at the tick boundary; print
  `/pr-converge <PR URL>` and the persisted phase.

Full portable rules:
[`../../_shared/pr-loop/portable-driver.md`](../../_shared/pr-loop/portable-driver.md).

## Bugteam execution

**Second audit** (BUGTEAM phase) is **always** **bugteam** skill: preflight,
CODE_RULES gate, **`code-quality-agent`** / **`clean-coder`** loop, audit
rubric, outcome shape, Step 2 BUGTEAM §(b)–(d) contract — all in
[`../../bugteam/SKILL.md`](../../bugteam/SKILL.md) plus `PROMPTS.md` / `EXAMPLES.md` /
`CONSTRAINTS.md`. Do not re-spec.

**pr-converge rule:** Prefer **`Skill({skill: "bugteam", args: "<PR URL or
args>"})`** wherever registry exposes `Skill`. When `Skill` not invokable
(typical delegated teammate), worker runs **bugteam** by loading
`../../bugteam/SKILL.md` from the same checkout. If bugteam cannot run, cancel the
convergence loop fully and report the issue to the user.
