---
name: pr-converge
description: >-
  Spawns a background subagent that drives the current PR to convergence by
  alternating Cursor Bugbot and the in-house bugteam audit. The subagent
  fetches each reviewer's findings, applies TDD fixes, pushes one commit per
  tick, replies inline, and re-triggers the reviewer. Termination requires a
  back-to-back clean cycle — bugbot CLEAN immediately followed by bugteam
  CLEAN with no intervening fixes — at which point the subagent marks the PR
  ready for review and terminates. Triggers: '/pr-converge', 'drive PR to
  convergence', 'loop bugbot and bugteam', 'babysit bugbot and bugteam',
  'until both are clean', 'converge this PR'.
---

# PR Converge

Delegates the bugbot ↔ bugteam convergence loop to a background subagent so the main session stays free. The subagent owns its own cadence and self-terminates on convergence or a hard blocker.

## When this skill applies

The user is on a PR branch and wants both reviewers — Cursor's Bugbot AND the in-house `/bugteam` audit — to keep re-reviewing after each push, with findings auto-addressed between ticks. The PR stays in draft until convergence; on convergence the subagent flips it to ready for review.

## The Process

### Step 1: Gather PR context

From the current repo:

```bash
gh pr view --json number,url,headRefOid,baseRefName,headRefName,isDraft
```

Capture `number`, `headRefOid`, owner/repo (from `url`), branch name, and current draft state. Pass these to the subagent so it can use them directly.

### Step 2: Spawn the background subagent

Invoke the `Agent` tool with:

- `subagent_type: "general-purpose"`
- `run_in_background: true`
- `description: "PR convergence loop for #<N>"`
- `prompt`: the full instructions in **Step 3 (Subagent prompt template)**, with placeholders filled in from Step 1.

Record the returned agent ID. Report to the user in one or two lines:

- The subagent is running in the background and will alternate bugbot ↔ bugteam.
- It self-terminates on back-to-back clean and flips the PR ready for review.
- To stop it early, the user says "stop the converge loop" and you call `TaskStop <agent_id>`.

The skill's job in the main session ends once the subagent is spawned and reported.

### Step 3: Subagent prompt template

Pass this verbatim to the subagent (substituting the bracketed values):

> You are driving PR **#[NUMBER]** at **[OWNER]/[REPO]** (branch `[BRANCH]`, current HEAD `[HEAD_SHA]`) to convergence by alternating Cursor Bugbot and the in-house bugteam audit. Your job: keep the loop running until BOTH reviewers return CLEAN against the same HEAD with no intervening fixes, then mark the PR ready for review and stop.
>
> **State you maintain across ticks** (keep it in your own working memory; you re-enter these instructions verbatim each wakeup):
>
> - `phase`: `BUGBOT` or `BUGTEAM`. Start in `BUGBOT`.
> - `bugbot_clean_at`: the HEAD SHA at which bugbot last reported clean, or `null`. Reset to `null` whenever you push a new commit.
> - `inline_lag_streak`: integer counter, initialized to `0`. Tracks consecutive ticks where bugbot's review body indicates findings against `current_head` but the inline-comments API returns zero matching comments. Reset to `0` on any other branch outcome.
>
> **Per-tick work** (do this now, then on each wakeup):
>
> 1. Resolve current HEAD: `gh api repos/[OWNER]/[REPO]/pulls/[NUMBER] --jq '.head.sha'`. Capture it as `current_head`.
>
> 2. Branch on `phase`:
>
>    **If `phase == BUGBOT`:**
>
>    a. Fetch the latest Cursor Bugbot review:
>       ```bash
>       gh api repos/[OWNER]/[REPO]/pulls/[NUMBER]/reviews \
>         --jq '[.[] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | last'
>       ```
>       Capture `commit_id`, `state`, `submitted_at`, and the body. Bugbot's body contains either `Cursor Bugbot has reviewed your changes and found <N> potential issue` (findings exist) or text indicating no issues found.
>
>    b. Fetch unaddressed inline comments from `cursor[bot]` on `current_head`:
>       ```bash
>       gh api repos/[OWNER]/[REPO]/pulls/[NUMBER]/comments \
>         --jq "[.[] | select(.user.login==\"cursor[bot]\") | select(.commit_id==\"$current_head\")]"
>       ```
>
>    c. Decide (the four branches below cover every input combination — match the first branch whose predicate holds):
>       - **No bugbot review yet, OR latest bugbot review's `commit_id` differs from `current_head`:** Re-trigger bugbot (step 3), set `bugbot_clean_at = null`, reset `inline_lag_streak = 0`, schedule next wakeup, return.
>       - **Latest review's `commit_id == current_head` AND zero unaddressed inline findings AND review body indicates clean:** Set `bugbot_clean_at = current_head`. Reset `inline_lag_streak = 0`. Transition `phase = BUGTEAM`. Continue to bugteam branch in this same tick — back-to-back convergence requires bugteam to run against the same HEAD before the next wakeup is scheduled.
>       - **Latest review's `commit_id == current_head` with unaddressed inline findings (review body indicates findings):** Apply the **Fix protocol** below to address them. Reset `inline_lag_streak = 0`. The fix protocol pushes a new commit, which sets `current_head` to the new SHA, sets `bugbot_clean_at = null`, replies inline on each thread, and re-triggers bugbot. Schedule next wakeup, return.
>       - **Latest review's `commit_id == current_head` AND review body indicates findings AND inline-comments API returns zero matching comments for `current_head`:** Treat as transient API propagation lag — bugbot publishes the review body and inline comments through separate API operations and the two writes can briefly desync. Increment `inline_lag_streak`. When `inline_lag_streak >= 3`, escalate as a hard blocker (bugbot review is structurally inconsistent — body claims findings while inline anchors stay empty across three consecutive ticks); report and terminate. Otherwise schedule next wakeup at `delaySeconds: 60` (lag is short-lived) and return; the inline comments should appear on the next tick.
>
>    **If `phase == BUGTEAM`:**
>
>    a. Run the in-house bugteam audit on the current PR:
>       ```bash
>       claude -p "/bugteam" --max-turns 200
>       ```
>       (The `/bugteam` skill audits the current PR against CODE_RULES, posts review threads, and converges or stops at its own internal cap. Wait for it to complete; capture exit and final summary.)
>
>    b. **Re-resolve current HEAD now** because `/bugteam` may have pushed commits during its run. The `current_head` from step 1 is potentially stale at this point:
>       ```bash
>       new_head=$(gh api repos/[OWNER]/[REPO]/pulls/[NUMBER] --jq '.head.sha')
>       ```
>       If `new_head != current_head`, set `current_head = new_head` AND set `bugbot_clean_at = null`. The new commits from bugteam invalidate bugbot's prior clean.
>
>    c. Inspect bugteam's output. Bugteam reports either `convergence (zero findings)` or a list of unfixed findings with file:line.
>
>    d. Decide based on the (post-bugteam) state — order matters; check pushed-during-bugteam FIRST so a convergence report against a stale HEAD never falsely terminates:
>       - **bugteam pushed during this tick (i.e., `bugbot_clean_at` was just reset to `null` in step b):** Re-trigger bugbot in this same tick (step 3) so the new HEAD enters bugbot's queue immediately, transition `phase = BUGBOT`, schedule next wakeup, return. The new commit needs a fresh bugbot review before convergence can be claimed.
>       - **bugteam reports convergence AND `bugbot_clean_at == current_head` (no push during this tick):** This is back-to-back clean. Mark the PR ready for review:
>         ```bash
>         gh pr ready [NUMBER] --repo [OWNER]/[REPO]
>         ```
>         Report to the parent in one sentence: "PR #[NUMBER] converged: bugbot CLEAN at [SHA], bugteam CLEAN at [SHA]; marked ready for review." Terminate; this is the final tick — skip scheduling the next wakeup.
>       - **bugteam reports convergence BUT `bugbot_clean_at != current_head` (no push during this tick):** Bugteam reached zero findings without committing, yet bugbot still needs re-confirmation against this HEAD. This branch is reachable only when state diverged BETWEEN ticks — for example, the user pushed a manual commit between two wakeups, leaving `current_head` ahead of the SHA bugbot last cleaned. Transition `phase = BUGBOT`, schedule next wakeup, return.
>       - **bugteam reports findings without committing fixes:** apply the **Fix protocol** below (which always re-triggers bugbot after the push), transition `phase = BUGBOT`, schedule next wakeup, return.
>
> 3. Re-trigger bugbot (used in step 2.c first branch, in step 2.d BUGTEAM branch 1, and in the Fix protocol). Post a literal `bugbot run` PR comment:
>    ```bash
>    printf 'bugbot run\n' > /tmp/bugbot-run.md
>    gh pr comment [NUMBER] --repo [OWNER]/[REPO] --body-file /tmp/bugbot-run.md
>    rm /tmp/bugbot-run.md
>    ```
>    Use the literal phrase `bugbot run` exactly — Cursor Bugbot's documented re-trigger phrase, empirically the only one that fires a fresh review.
>
> 4. Schedule the next wakeup with `ScheduleWakeup` using a single rule: `delaySeconds: 300` whenever bugbot was just re-triggered (whether by step 3 directly, by the Fix protocol's mandatory re-trigger, or by BUGTEAM branch 1's same-tick re-trigger). Bugbot finishes a review in 1–4 minutes, so 300s gives a one-minute safety margin past the upper bound. The single exception is the BUGBOT inline-lag branch, which uses `delaySeconds: 60` because no re-trigger fired and the only thing being awaited is GitHub's inline-comments API catching up. Set `reason` to one short sentence on what is being awaited, including the current `phase` and `bugbot_clean_at` SHA when set; set `prompt` to the literal sentinel `<<autonomous-loop-dynamic>>` so the next firing re-enters these instructions.
>
> **Fix protocol** (used by both phases when findings exist):
>
> - Read each referenced file:line.
> - Write a failing test first when the finding has behavior to test. For pure doc, comment, or naming nits with no behavior, go straight to the fix.
> - Implement the fix.
> - Stage the affected files and create one new commit on the existing branch:
>   ```bash
>   git add <files> && git commit -m "fix(review): <brief summary>"
>   ```
>   Honor pre-commit and pre-push hooks; when a hook rejects, read its message, fix the underlying issue, retry. Hook rejections flag real underlying issues worth investigating.
> - Push the new commit:
>   ```bash
>   git push origin [BRANCH]
>   ```
>   Capture the new HEAD SHA. Set `current_head` to it. Set `bugbot_clean_at = null`.
> - Reply inline on each addressed comment thread:
>   ```bash
>   gh api -X POST repos/[OWNER]/[REPO]/pulls/[NUMBER]/comments/<comment_id>/replies \
>     -f body="Addressed in <new_sha>. <one-line description of the fix>."
>   ```
>   Use `--body-file` when the body contains backticks (per repo policy on `gh` body content).
> - **Always re-trigger bugbot (step 3 above) after pushing a fix**, regardless of which phase originated the findings. Any new commit invalidates bugbot's prior clean by definition, so bugbot must re-review the new HEAD before convergence can be claimed. Re-triggering in the same tick saves a full wakeup cycle compared to deferring the trigger to the next tick — the fix protocol's last step before scheduling the wakeup is always `printf 'bugbot run\n' > /tmp/bugbot-run.md && gh pr comment ... --body-file /tmp/bugbot-run.md && rm /tmp/bugbot-run.md`.
>
> **Stop conditions:**
>
> - **Convergence** (back-to-back clean as defined in step 2.d BUGTEAM second branch — `bugteam reports convergence AND bugbot_clean_at == current_head` with no push during this tick): mark PR ready for review, report one-sentence summary to parent, terminate.
> - **Hard blocker:** API auth failure persists across two ticks, a CI regression whose root cause falls outside this PR, a hook rejection investigated through three commits and still unresolved, `inline_lag_streak >= 3`, or `/bugteam` itself reports a stuck state. Report the specific blocker and your diagnosis to the parent, then terminate; skip scheduling the next wakeup.
> - **Parent sends `TaskStop`:** terminate immediately.
>
> **Safety cap:** when 30 ticks elapse before convergence, stop and report. That many rounds means something structural is wrong with the loop. (Higher than copilot-review's 20-tick cap because two reviewers run sequentially per round.)

### Step 4: Report back to the user

After spawning, tell the user in one or two lines: subagent ID, PR URL, that it will alternate bugbot and bugteam and notify on convergence or blocker. Nothing else.

## Stopping the subagent

- Convergence → subagent stops itself, marks PR ready for review.
- Blocker → subagent reports and stops.
- User says stop → `TaskStop <agent_id>`.
- User asks what loops are running → `TaskList`.

## Ground rules (for the subagent)

- **Append commits.** Each tick adds at most one new fix commit. Multiple findings within one tick collapse into a single commit; the next tick handles the next round.
- **`bugbot_clean_at` resets on every push.** A new commit invalidates bugbot's prior clean by definition — bugbot must re-review the new HEAD before convergence can be claimed.
- **Back-to-back clean is the ONLY termination criterion.** Convergence requires both reviewers clean against the same HEAD with no intervening fixes; either reviewer clean alone counts as in-progress.
- **The `bugbot run` comment is load-bearing.** Use the literal phrase `bugbot run` exactly — empirically the only re-trigger Cursor Bugbot recognizes; alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.
- **`gh pr ready` is the convergence action.** Mark the PR ready for review and stop there. Merge, additional reviewers, title, and body remain the user's decisions; the subagent's contract ends at "ready for review."
- **Honor pre-push and pre-commit hooks.** When a hook rejects the change, read its output, fix the underlying issue (the failing test, the missing constant, the broken import), and retry.

## Examples

<example>
User: `/pr-converge`
Claude: [reads PR context, spawns background subagent with the Step 3 template, reports "subagent X driving PR #280 to convergence; will notify on back-to-back clean"]
</example>

<example>
User: "drive this PR to convergence — bugbot and bugteam until both are clean"
Claude: [same as above]
</example>

<example>
Subagent tick fires in BUGBOT phase, latest bugbot review is against an older commit.
Subagent: [posts `bugbot run` comment, sets `bugbot_clean_at = null`, schedules next wakeup at 300s, returns]
</example>

<example>
Subagent tick fires in BUGBOT phase, bugbot has 2 unaddressed findings on HEAD.
Subagent: [TDD-fixes both, one commit, pushes, replies inline on both threads, posts `bugbot run`, schedules next wakeup at 300s, returns]
</example>

<example>
Subagent tick fires in BUGBOT phase, bugbot is clean against HEAD.
Subagent: [sets `bugbot_clean_at = HEAD`, transitions `phase = BUGTEAM`, runs `/bugteam` in the same tick]
</example>

<example>
Subagent in BUGTEAM phase, /bugteam reports convergence and `bugbot_clean_at == current_head`.
Subagent: [runs `gh pr ready [NUMBER]`, reports "PR converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for review", terminates]
</example>

<example>
Subagent in BUGTEAM phase, /bugteam pushed a fix commit during its run.
Subagent: [re-resolves HEAD, sets `bugbot_clean_at = null`, posts `bugbot run` in this same tick, transitions `phase = BUGBOT`, schedules next wakeup at 300s]
</example>

<example>
Subagent tick fires in BUGBOT phase, bugbot review body says "found 3 potential issues" against HEAD but the inline-comments API returns zero matching comments for `current_head`.
Subagent: [increments `inline_lag_streak` to 1, schedules next wakeup at 60s, returns; expects inline comments to appear by the next tick]
</example>
