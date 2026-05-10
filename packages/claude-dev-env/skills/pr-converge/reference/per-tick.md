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
workflow file specifies delays, prompts, convergence cleanup, and
inline-lag handling.

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

Capture `number`, `head.sha` (= `current_head`), owner/repo, branch.

## Step 2: Branch on `phase`

### `phase == COPILOT_WAIT`

Re-enter convergence-gates.md gate (d) Copilot-response handling:

a. Fetch latest Copilot review at `current_head`:

   ```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_reviews")
   → filter `.user.login` for copilot (case-insensitive substring "copilot")
   → filter `.commit_id == current_head`
   → sort by `.submitted_at` descending
   ```

b. Decide:
   - **Copilot review present at `current_head`:**
     - `state: APPROVED` → reset `copilot_wait_count = 0`, set `copilot_clean_at = current_head`, `phase = BUGTEAM`.
       Continue to convergence-gates.md gate (e) in same tick.
     - `state: CHANGES_REQUESTED` or `COMMENTED` with non-empty body → dirty.
       Reset `copilot_wait_count = 0`. Apply **Fix protocol**.
       Reset `bugbot_clean_at = null` AND
       `copilot_clean_at = null`, `phase = BUGBOT`, schedule next wakeup, return.
   - **No Copilot review at `current_head` yet:** Increment `copilot_wait_count`.
     `>= 3` → hard blocker per [stop-conditions.md](stop-conditions.md); report
     and terminate with no loop pacing. Else schedule next wakeup (270s), return.

### `phase == BUGBOT`

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

b. Fetch unaddressed inline comments from `cursor[bot]` for newest Bugbot
review on `current_head`:

   ```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_review_comments")
   → filter threads where `is_outdated == false` AND `is_resolved == false`
     AND any comment has `.author` matching cursor/bugbot (case-insensitive substring)
   ```

c. Decide (four branches; match first whose predicate holds):
   - **No bugbot review yet, OR latest review's `commit_id` ≠
     `current_head`:** Re-trigger bugbot (Step 3), set `bugbot_clean_at =
     null`, reset `inline_lag_streak = 0`, schedule next wakeup, return.
   - **`commit_id == current_head` AND zero unaddressed inline AND review
     body clean:** Set `bugbot_clean_at = current_head`, reset
     `inline_lag_streak = 0`, `phase = BUGTEAM`. Continue BUGTEAM in same
     tick — back-to-back convergence requires bugteam on same HEAD
     before next wakeup.
   - **`commit_id == current_head` with unaddressed inline findings:**
     Apply **Fix protocol**. Reset `inline_lag_streak = 0`. With
     `state.json`: clean-coder teammate pushes, replies inline, writes
     `state.json`, goes idle; Step 3 on new HEAD runs after via
     orchestrator-spawned follow-up agent (§Fix result → general-purpose).
     No `state.json` (single-PR): spawn Agent (subagent_type: clean-coder) to implement → push → reply inline on each thread
     via `add_reply_to_pull_request_comment` MCP → Step 3 in same tick (see
     [Single-PR fix workflow](fix-protocol.md#single-pr-fix-workflow) for
     full contract).
     Schedule next wakeup, return.
   - **`commit_id == current_head` AND review body findings AND inline
     API zero matching for `current_head`:** Transient API lag. Increment
     `inline_lag_streak`. `>= 3` → hard blocker; report and terminate with
     no loop pacing. Else Step 4 uses the BUGBOT inline-lag section of
     `../workflows/schedule-wakeup-loop.md` (`delaySeconds: 90`).

### `phase == BUGTEAM`

a. Run **bugteam** on current PR.

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

   If `new_head != current_head`, set `current_head = new_head` AND
   `bugbot_clean_at = null`. New commits invalidate bugbot's prior clean.

c. Inspect bugteam outcome. Reports `convergence (zero findings)` or list
of unfixed findings with file:line.

d. Decide based on post-bugteam state — order matters. Check
pushed-during-bugteam FIRST so convergence report against stale HEAD
never falsely terminates:
   - **Audit pushed this tick (`bugbot_clean_at` reset in step b):**
     Re-trigger bugbot same tick (Step 3) so new HEAD enters queue, `phase
     = BUGBOT`, schedule next wakeup, return.
   - **Convergence AND `bugbot_clean_at == current_head` (no push):**
     Back-to-back clean — necessary, not sufficient. Run **[convergence-gates.md](convergence-gates.md)** to clear Copilot, Claude, mergeability, post-convergence
     Copilot-request, and thread-resolution gates. Only when all five gates pass mark PR ready and
     **omit loop pacing** per **Convergence** of active pacing workflow.
   - **Convergence BUT `bugbot_clean_at != current_head` (no push):**
     `phase = BUGBOT`, schedule next wakeup, return.
   - **Findings without committed fixes:** spawn Agent (subagent_type: clean-coder) to implement fixes and push, then reply inline via `add_reply_to_pull_request_comment` MCP, following [Single-PR fix workflow](fix-protocol.md#single-pr-fix-workflow).
     `phase = BUGBOT`, schedule next wakeup, return.

## Step 3: Re-trigger bugbot

Use the `add_issue_comment` MCP tool:

    add_issue_comment(owner="OWNER", repo="REPO", issueNumber=NUMBER, body="bugbot run")

`bugbot run` is empirically the only re-trigger Cursor Bugbot recognizes;
alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

**Gotcha (duplicate `bugbot run` while review queued):** Skip Step 3 when
the latest `bugbot run` PR comment has an `:eyes:` or `:+1:` reaction; wait
for review or HEAD change before re-triggering.

## Step 4: Loop pacing

**`ScheduleWakeup` field hints** (prefer [Pacing
workflow](#pacing-workflow)):

- `delaySeconds: 270` after bugbot re-trigger. Bugbot finishes in 1–4
  min; 270s stays under 5-min prompt-cache TTL with margin. Exception:
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
