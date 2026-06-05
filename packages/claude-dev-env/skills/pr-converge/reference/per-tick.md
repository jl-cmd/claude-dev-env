# Per-tick work

Use on **draft PR**. Cursor Bugbot and `/bugteam` re-run after each push. Fix
findings between rounds until back-to-back clean on same `HEAD`, then mark
PR ready for review.

Run every tick in parent harness session. Pacing lives in
[`../workflows/schedule-wakeup-loop.md`](../workflows/schedule-wakeup-loop.md) (read before Step 4); see [Pacing
workflow](#pacing-workflow).

Every BUGTEAM tick runs **bugteam** — never hand-rolled substitute. Fix
protocol per [fix-protocol.md](fix-protocol.md). Pacing stays in main session via
`ScheduleWakeup` (pre-flight aborts when absent).

## Invocation modes

- **`/pr-converge`** runs one tick, then Step 4 schedules the next via
  `ScheduleWakeup`. Omit the next wakeup only on convergence or **Stop
  conditions**.

## Pacing workflow

Read [`../workflows/schedule-wakeup-loop.md`](../workflows/schedule-wakeup-loop.md)
(installed copy under `$HOME/.claude/skills/pr-converge/workflows/`) before
Step 4. The pre-flight gate guarantees `ScheduleWakeup` is invokable; the
workflow file specifies delays, prompts, and convergence cleanup.

- **`/pr-converge`** (default): loops until convergence. After each tick
  (unless converged or stopped), run **Step 4**.

## Step 1: Resolve current HEAD and PR context

Read prior tick's state line from most recent assistant message (or
initialize fields if none). Increment `tick_count` by 1 in conversation
state line when **no** `state.json` (single-PR only). With `state.json`, do
**not** increment here — orchestrator's per-tick bump is sole increment.

```bash
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get") → `.head.sha`
```

If owner/repo/number are not yet known, extract them from the PR URL.
If `current_head` changed since last tick, reset `bugbot_down` to `false`
(new HEAD invalidates prior down-detection state).

Capture `number`, `head.sha` (= `current_head`), owner/repo, branch.

## Step 2: Branch on `phase`

### `phase == BUGBOT`

**Opt-out gate (runs first, before any fetch or trigger).**
`python "$HOME/.claude/_shared/pr-loop/scripts/reviews_disabled.py" --reviewer bugbot`

- Exit 0 (`CLAUDE_REVIEWS_DISABLED` lists `bugbot`) → set `bugbot_down = true`,
  `phase = CODE_REVIEW`, continue CODE_REVIEW in the same tick; skip steps a–c below.
- Exit 1 → proceed to step a.

Because `bugbot_down` resets on every push, this gate re-runs on every
BUGBOT entry and keeps Cursor Bugbot skipped for the entire run.

a. Fetch Cursor Bugbot reviews newest-first, walk back until first clean:

   ```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_reviews")
   → filter `.user.login` for cursor/bugbot, sort by `.submitted_at` descending
   ```

   Track dirty entries (review body contains `BUGBOT_REVIEW` markers with finding content); Fix protocol reads them back later this tick.

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

   For each unresolved thread, you still need to know **who** wrote it
   and **what commit** it anchors to so you can decide how to address it
   — but the gate itself doesn't filter on those fields. Verify each
   thread's concern against current HEAD; either fix-and-resolve or
   reply-with-note-and-resolve.

c. Decide (four branches; match first whose predicate holds):
   - **No bugbot review yet, OR latest review's `commit_id` ≠
     `current_head`:** Re-trigger bugbot (Step 3), set `bugbot_clean_at =
     null`, reset `inline_lag_streak = 0`, schedule next wakeup, return.
   - **`commit_id == current_head` AND zero unaddressed inline AND review
     body clean:** Set `bugbot_clean_at = current_head`, reset
     `inline_lag_streak = 0`, `phase = CODE_REVIEW`. Continue CODE_REVIEW
     in same tick — back-to-back convergence requires code-review then
     bugteam on same HEAD before next wakeup.
   - **`commit_id == current_head` with unaddressed inline findings:**
     Apply **Fix protocol**. Reset `inline_lag_streak = 0`. With
     `state.json`: clean-coder teammate pushes, replies inline, writes
     `state.json`, goes idle; Step 3 on new HEAD runs after via
     orchestrator-spawned follow-up agent (§Fix result → general-purpose).
     No `state.json` (single-PR): spawn Agent (subagent_type: clean-coder) to implement → push → reply inline on each thread
     via `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py` → Step 3 in same tick (see
     [Single-PR fix workflow](fix-protocol.md#single-pr-fix-workflow) for
     full contract).
     Schedule next wakeup, return.

### `phase == CODE_REVIEW`

Local correctness/quality pass between BUGBOT clean and BUGTEAM. Enters
after BUGBOT reports clean on `current_head` (or `bugbot_down == true`).
Runs Claude Code's built-in `/code-review --fix` on the full
`origin/main...HEAD` diff; it produces no GitHub review artifact, so there
are no code-review threads to resolve.

a. Run Claude Code's built-in `/code-review --fix` on the FULL
   `origin/main...HEAD` diff — every file the PR touches — via the
   [local diff review](https://code.claude.com/docs/en/code-review#review-a-diff-locally).
   It reviews the diff and applies its findings to the working tree.

   Before running, confirm the working tree sits on the PR's HEAD with no
   uncommitted edits, then invoke `/code-review --fix` with no path
   arguments so it audits the whole branch diff against `origin/main`. Do
   not delta-scope to commits added since the prior clean SHA, do not
   scope to a single file, do not scope to bugbot's flagged paths. A
   partial-scope round does not count and cannot set
   `code_review_clean_at`. Pass no effort argument, so the review uses
   the session's current effort.

b. Decide (two branches; match first whose predicate holds):

   - **`/code-review` applied fixes (working tree changed):** Commit the
     applied fixes in one commit → push, following [Single-PR fix
     workflow](fix-protocol.md#single-pr-fix-workflow). Reset
     `bugbot_clean_at = null` AND `code_review_clean_at = null`. Re-trigger
     bugbot (Step 3) so the new HEAD enters the queue. Set `phase = BUGBOT`,
     schedule next wakeup, return. A code-review fix push requires a full
     back-to-back-clean cycle on the new HEAD.
   - **Clean (no changes applied):** Set
     `code_review_clean_at = current_head`, `phase = BUGTEAM`. Continue
     BUGTEAM in same tick — back-to-back convergence requires bugbot,
     code-review, and bugteam all clean on the same HEAD.

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

   If `new_head != current_head`, set `current_head = new_head`,
   `bugbot_clean_at = null`, `bugbot_down = false`. New commits invalidate
   bugbot's prior clean and down-detection state.

c. Inspect bugteam outcome. Reports `convergence (zero findings)` or list
of unfixed findings with file:line.

d. Decide based on post-bugteam state — order matters. Check
pushed-during-bugteam FIRST so convergence report against stale HEAD
never falsely terminates:
   - **Audit pushed this tick (`bugbot_clean_at` reset in step b):**
     Re-trigger bugbot same tick (Step 3) so new HEAD enters queue, `phase
     = BUGBOT`, schedule next wakeup, return.
   - **Convergence AND `bugbot_clean_at == current_head` (no push):**
     Back-to-back clean — necessary, not sufficient. Run **[convergence-gates.md](convergence-gates.md)** to clear all six gates: Copilot findings,
     Claude reviewer, mergeability, post-convergence Copilot request,
     thread resolution. Only when all six gates pass mark PR ready and
     **omit loop pacing** per **Convergence** of active pacing workflow.
   - **Convergence BUT `bugbot_clean_at != current_head` (no push):**
     `phase = BUGBOT`, schedule next wakeup, return.
   - **Findings without committed fixes:** spawn Agent (subagent_type: clean-coder) to implement fixes and push, then reply inline via `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py`, following [Single-PR fix workflow](fix-protocol.md#single-pr-fix-workflow).
     `phase = BUGBOT`, schedule next wakeup, return.

### `phase == COPILOT_WAIT`

Post-convergence Copilot re-check. Enters after gate (d) requests Copilot
review. Do **not** run bugteam here — that only happens after BUGBOT clean
on this HEAD.

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
     `copilot_clean_at = current_head`. Record "Copilot APPROVED". Set
     `phase = BUGTEAM`. Continue to convergence-gates.md gate (b) in same
     tick — back-to-back convergence requires all gates on same HEAD.
   - **Copilot review dirty (CHANGES_REQUESTED or COMMENTED with findings)
     at `current_head`:** Apply **Fix protocol** — spawn Agent
     (subagent_type: clean-coder) to implement → push → reply inline on each
     thread via `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py`. For body-only
     findings (no inline threads), post top-level review reply citing new
     HEAD SHA. Reset
     `bugbot_clean_at = null` AND `copilot_clean_at = null`. **Set
     `phase = BUGBOT`** (NOT COPILOT_WAIT) — every fix push requires a full
     back-to-back-clean cycle on the new HEAD. Schedule next wakeup, return.
   - **No Copilot review at `current_head` yet:** Increment
     `copilot_wait_count` (init 0 on COPILOT_WAIT entry; reset to 0 on
     every push and on every successful Copilot review). `>= 3` → hard
     blocker per [stop-conditions.md](stop-conditions.md). Otherwise
     schedule next wakeup (360s), return.

**Non-negotiable:** After any Copilot fix push, `phase` MUST route to
`BUGBOT`. Never cycle COPILOT_WAIT → fix → COPILOT_WAIT. The
back-to-back-clean guarantee (bugbot ∧ bugteam both clean on same HEAD
before gates re-open) only holds when every fix commit re-enters through
BUGBOT.

## Step 3: Re-trigger bugbot

- [ ] **Opt-out gate.** Enforced at BUGBOT entry (see `### phase == BUGBOT`).
  When `CLAUDE_REVIEWS_DISABLED` lists `bugbot`, the entry gate sets
  `bugbot_down = true` and routes to BUGTEAM before any trigger flow runs,
  so the checks below are skipped.
- [ ] **Silent-pass pre-check.** Run `python ~/.claude/skills/pr-converge/scripts/check_bugbot_ci.py --check-clean --owner <O> --repo <R> --sha <current_head>`
- [ ] Exit 0 → bugbot CI completed clean with no review (silent pass); set `bugbot_clean_at = current_head`, `phase = CODE_REVIEW`, continue CODE_REVIEW same tick
- [ ] Exit 1 (not a silent pass) or Exit 2 (gh CLI error — silent pass not confirmable) → continue with the trigger flow below
- [ ] Run `python ~/.claude/skills/pr-converge/scripts/check_bugbot_ci.py --check-active --owner <O> --repo <R> --sha <current_head>`
- [ ] Exit 0 → bugbot already queued on this commit; skip posting, wait for completion
- [ ] Exit 1 → post trigger via `add_issue_comment(owner="OWNER", repo="REPO", issueNumber=NUMBER, body="bugbot run")`
- [ ] Wait 8s
- [ ] Run `python ~/.claude/skills/pr-converge/scripts/check_bugbot_ci.py --owner <O> --repo <R> --sha <current_head>`
- [ ] Exit non-zero → bugbot is down; set `bugbot_down = true`, `phase = CODE_REVIEW`, continue CODE_REVIEW same tick
- [ ] Exit 0 (check run present) → record `bugbot_acknowledged_at = <now ISO 8601>`, proceed to Step 4

The silent-pass pre-check fires FIRST so we never re-trigger a bot that
already finished cleanly. Cursor Bugbot communicates "no findings" by
completing the CI check with `conclusion: success` (or `neutral`) and
posting no review. The pre-check treats that outcome as
`bugbot_clean_at = current_head`, equivalent to an explicit clean
review. Without it, the trigger flow would re-prompt a bot that has
already evaluated this commit and refuses to re-run, and the bypass
branch would falsely mark `bugbot_down = true`.

`bugbot run` is empirically the only re-trigger Cursor Bugbot recognizes;
alternative phrasings silently no-op.

## Step 4: Loop pacing

**`ScheduleWakeup` field hints** (prefer [Pacing
workflow](#pacing-workflow)):

- `delaySeconds: 360` after bugbot re-trigger. Exception:
  BUGBOT inline-lag branch uses `delaySeconds: 90` (no re-trigger;
  awaiting GitHub inline API).
- `reason`: short sentence on what is awaited, including `phase` and
  `bugbot_clean_at` SHA.
- `prompt: "/pr-converge"`.

**On convergence:** apply **Convergence** section of
`../workflows/schedule-wakeup-loop.md` (omit wakeups).

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
