---
name: pr-converge
description: >-
  Drives the current PR to convergence by alternating Cursor Bugbot and the
  in-house bugteam audit. Each invocation runs one tick of work in the main
  session: fetches the latest reviewer state, applies TDD fixes for any
  findings, pushes one commit per tick, replies inline, and re-triggers the
  reviewer. To loop automatically, invoke as `/loop /pr-converge` — the /loop
  skill self-paces re-entry via ScheduleWakeup. Convergence requires a
  back-to-back clean cycle (bugbot CLEAN immediately followed by bugteam CLEAN
  with no intervening fixes), at which point the PR is flipped to ready for
  review and the loop terminates. Triggers: '/pr-converge', 'drive PR to
  convergence', 'loop bugbot and bugteam', 'babysit bugbot and bugteam',
  'until both are clean', 'converge this PR'.
---

# PR Converge

Runs one tick of the bugbot ↔ bugteam convergence loop in the main session. Designed to be invoked under `/loop /pr-converge` so the parent's ScheduleWakeup paces re-entry. Self-terminates the loop on convergence (back-to-back clean) by flipping the PR to ready for review and omitting the next ScheduleWakeup.

## Why the work runs in the main session, not a background subagent

`ScheduleWakeup` is a primitive of the parent harness; it is not exposed to `general-purpose` subagents. A prior version of this skill spawned a background subagent and instructed it to call `ScheduleWakeup` at the end of each tick. The subagent's tool registry returned "No matching deferred tools found" for `ScheduleWakeup`, so the loop could never self-perpetuate — it ran exactly one tick and stalled. Running the loop in the main session via `/loop /pr-converge` puts the work on the same harness that owns `ScheduleWakeup`, eliminating that failure mode.

## When this skill applies

The user is on a PR branch and wants both reviewers — Cursor's Bugbot AND the in-house `/bugteam` audit — to keep re-reviewing after each push, with findings auto-addressed between ticks. The PR stays in draft until convergence; on convergence the skill flips it to ready for review.

## Invocation modes

- **`/loop /pr-converge`** (recommended): loops automatically. The /loop skill runs each tick and uses ScheduleWakeup to pace re-entry. Termination on convergence is automatic; the skill omits the next wakeup at the convergence tick.
- **`/pr-converge`** (manual): runs exactly one tick and returns. Useful for ad-hoc state checks or for advancing the loop one step manually. The user re-runs the skill (or wraps it in `/loop`) to continue.

## State across ticks

Track the following in plain text in the assistant's response so subsequent ticks can re-read it from conversation context:

- `phase`: `BUGBOT` or `BUGTEAM`. Start in `BUGBOT` on the first tick of a fresh loop.
- `bugbot_clean_at`: the HEAD SHA at which bugbot last reported clean, or `null`. Reset to `null` whenever a new commit is pushed.
- `inline_lag_streak`: integer counter, initialized to `0`. Tracks consecutive ticks where bugbot's review body indicates findings against `current_head` but the inline-comments API returns zero matching comments. Reset to `0` on any other branch outcome.
- `tick_count`: integer, initialized to `0`. Increment on every tick to enforce the safety cap.

Each tick begins by reading the prior tick's state line from the most recent assistant message and ends by emitting the updated state line.

## Per-tick work

### Step 1: Resolve current HEAD and PR context

Read the prior tick's state line from the most recent assistant message (or initialize all fields if none). **Increment `tick_count` by 1.** This is the increment referenced in the **State across ticks** section; without it the safety cap (Step 3.5, §Safety cap) never fires.

```bash
gh pr view --json number,url,headRefOid,baseRefName,headRefName,isDraft
```

Capture `number` (`<NUMBER>`), `headRefOid` (`current_head`), owner/repo (from `url`), branch name (`<BRANCH>`).

### Step 2: Branch on `phase`

#### `phase == BUGBOT`

a. Fetch Cursor Bugbot reviews newest-first and walk backwards until the first clean review:

   ```bash
   gh api repos/<OWNER>/<REPO>/pulls/<NUMBER>/reviews \
     --jq '[.[] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | reverse'
   ```

   Track dirty reviews in a temp file as you walk; the Fix protocol reads it back later in this tick:

   ```bash
   dirty_reviews_path=$(mktemp "${TMPDIR:-/tmp}/pr-converge-bugbot.XXXXXX")
   : > "$dirty_reviews_path"
   ```

   Iterate from index 0 (most recent) toward older entries:

   - Classify each review's body — **dirty** when it contains `Cursor Bugbot has reviewed your changes and found <N> potential issue`; **clean** otherwise.
   - For a dirty review, append one JSON line to `$dirty_reviews_path` with `{review_id, commit_id, submitted_at, body}`.
   - Stop at the first clean review. Older reviews are presumed addressed at that clean checkpoint and are not re-read.
   - When index 0 is itself clean, `$dirty_reviews_path` stays empty.

   Capture `commit_id`, `state`, `submitted_at`, and body of the index-0 review for the decision branches below. When a branch routes to the **Fix protocol**, read every entry from `$dirty_reviews_path` and address all of them — not just index 0.

b. Fetch unaddressed inline comments from `cursor[bot]` on `current_head`:
   ```bash
   gh api repos/<OWNER>/<REPO>/pulls/<NUMBER>/comments \
     --jq "[.[] | select(.user.login==\"cursor[bot]\") | select(.commit_id==\"$current_head\")]"
   ```

c. Decide (the four branches below cover every input combination — match the first branch whose predicate holds):
   - **No bugbot review yet, OR latest bugbot review's `commit_id` differs from `current_head`:** Re-trigger bugbot (Step 3), set `bugbot_clean_at = null`, reset `inline_lag_streak = 0`, schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND zero unaddressed inline findings AND review body indicates clean:** Set `bugbot_clean_at = current_head`. Reset `inline_lag_streak = 0`. Transition `phase = BUGTEAM`. Continue to bugteam branch in this same tick — back-to-back convergence requires bugteam to run against the same HEAD before the next wakeup is scheduled.
   - **Latest review's `commit_id == current_head` with unaddressed inline findings (review body indicates findings):** Apply the **Fix protocol** below to address them. Reset `inline_lag_streak = 0`. The fix protocol pushes a new commit, which sets `current_head` to the new SHA, sets `bugbot_clean_at = null`, replies inline on each thread, and re-triggers bugbot. Schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND review body indicates findings AND inline-comments API returns zero matching comments for `current_head`:** Treat as transient API propagation lag — bugbot publishes the review body and inline comments through separate API operations and the two writes can briefly desync. Increment `inline_lag_streak`. When `inline_lag_streak >= 3`, escalate as a hard blocker (bugbot review is structurally inconsistent — body claims findings while inline anchors stay empty across three consecutive ticks); report and terminate. Otherwise schedule next wakeup at `delaySeconds: 60` (lag is short-lived) and return; the inline comments should appear on the next tick.

#### `phase == BUGTEAM`

a. Run the in-house bugteam audit on the current PR by invoking the `Skill` tool in the main session:

   ```
   Skill({skill: "bugteam", args: "https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"})
   ```

   The main session is the team lead, so `TeamCreate` fires from the orchestrator and `/bugteam` emits its CODE_RULES gate output, teammate spawn lines, and audit progress as expected. The skill audits the current PR against CODE_RULES, posts review threads, and converges or stops at its own internal cap. Wait for it to complete; capture exit and final summary.

b. **Re-resolve current HEAD now** because `/bugteam` may have pushed commits during its run. The `current_head` from Step 1 is potentially stale at this point:
   ```bash
   new_head=$(gh api repos/<OWNER>/<REPO>/pulls/<NUMBER> --jq '.head.sha')
   ```
   If `new_head != current_head`, set `current_head = new_head` AND set `bugbot_clean_at = null`. The new commits from bugteam invalidate bugbot's prior clean.

c. Inspect bugteam's output. Bugteam reports either `convergence (zero findings)` or a list of unfixed findings with file:line.

d. Decide based on the (post-bugteam) state — order matters; check pushed-during-bugteam FIRST so a convergence report against a stale HEAD never falsely terminates:
   - **bugteam pushed during this tick (i.e., `bugbot_clean_at` was just reset to `null` in step b):** Re-trigger bugbot in this same tick (Step 3) so the new HEAD enters bugbot's queue immediately, transition `phase = BUGBOT`, schedule next wakeup, return. The new commit needs a fresh bugbot review before convergence can be claimed.
   - **bugteam reports convergence AND `bugbot_clean_at == current_head` (no push during this tick):** This is back-to-back clean. Mark the PR ready for review:
     ```bash
     gh pr ready <NUMBER> --repo <OWNER>/<REPO>
     ```
     Report to the user in one sentence: "PR #<NUMBER> converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for review." **Omit the next ScheduleWakeup call** — this terminates the /loop.
   - **bugteam reports convergence BUT `bugbot_clean_at != current_head` (no push during this tick):** Bugteam reached zero findings without committing, yet bugbot still needs re-confirmation against this HEAD. This branch is reachable only when state diverged BETWEEN ticks — for example, the user pushed a manual commit between two wakeups, leaving `current_head` ahead of the SHA bugbot last cleaned. Transition `phase = BUGBOT`, schedule next wakeup, return.
   - **bugteam reports findings without committing fixes:** apply the **Fix protocol** below (which always re-triggers bugbot after the push), transition `phase = BUGBOT`, schedule next wakeup, return.

### Step 3: Re-trigger bugbot

Used in Step 2 BUGBOT branch 1, in Step 2 BUGTEAM branch 1, and in the Fix protocol. Post a literal `bugbot run` PR comment. Write the body via the Write tool to a temp file, then pass it with `--body-file` (per the gh-body-file rule):

```bash
gh pr comment <NUMBER> --repo <OWNER>/<REPO> --body-file <path/to/bugbot_run.md>
```

The body file contains exactly the literal phrase `bugbot run` followed by a newline. Use that phrase exactly — empirically the only re-trigger Cursor Bugbot recognizes; alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

### Step 3.5: Enforce the safety cap

Before scheduling the next wakeup, evaluate `tick_count`. When `tick_count >= 30`, stop and report per the **Stop conditions** safety-cap branch (§Safety cap) — **omit Step 4 entirely**. Reaching this many rounds means something structural is wrong with the loop and continuing wastes work. Otherwise proceed to Step 4.

### Step 4: Schedule the next wakeup (only when invoked under `/loop`)

**Skip this step entirely when the skill was invoked as bare `/pr-converge`** (manual mode). Manual mode runs exactly one tick and returns without scheduling — the user re-runs the skill or wraps it in `/loop` to continue. References elsewhere in this document to "schedule next wakeup, return" mean Step 4 below; under manual mode every such reference becomes "return" only.

Detect manual mode by inspecting the conversation context: when the most recent user message that triggered this run was `/pr-converge` (no `/loop` prefix and no prior `ScheduleWakeup` chain entry that fired with `prompt: "/loop /pr-converge"`), this is manual mode. When the run was triggered by the parent's /loop wakeup chain or the user typed `/loop /pr-converge`, this is loop mode.

In **loop mode**, call `ScheduleWakeup` with:

- `delaySeconds: 270` whenever bugbot was just re-triggered (whether by Step 3 directly, by the Fix protocol's mandatory re-trigger, or by BUGTEAM branch 1's same-tick re-trigger). Bugbot finishes a review in 1–4 minutes, so 270s stays under the 5-minute prompt-cache TTL while giving a margin past bugbot's typical upper bound. The single exception is the BUGBOT inline-lag branch, which uses `delaySeconds: 60` because no re-trigger fired and the only thing being awaited is GitHub's inline-comments API catching up.
- `reason`: one short sentence on what is being awaited, including the current `phase` and `bugbot_clean_at` SHA when set.
- `prompt: "/loop /pr-converge"` — re-enters this skill via /loop on the next firing.

**On convergence (loop mode):** omit the ScheduleWakeup call entirely. The /loop terminates because no next wakeup was scheduled.

## Fix protocol

Used by both phases when findings exist:

- Read each referenced file:line.
- Write a failing test first when the finding has behavior to test. For pure doc, comment, or naming nits with no behavior, go straight to the fix.
- Implement the fix.
- Stage the affected files and create one new commit on the existing branch:
  ```bash
  git add <files> && git commit -m "fix(review): <brief summary>"
  ```
  Honor pre-commit and pre-push hooks; when a hook rejects, read its message, fix the underlying issue, retry. Hook rejections flag real underlying issues worth investigating.
- Push the new commit:
  ```bash
  git push origin <BRANCH>
  ```
  Capture the new HEAD SHA. Set `current_head` to it. Set `bugbot_clean_at = null`.
- Reply inline on each addressed comment thread using `--body-file` (per gh-body-file rule):
  ```bash
  gh api -X POST repos/<OWNER>/<REPO>/pulls/<NUMBER>/comments/<comment_id>/replies \
    --field body=@<path/to/reply.md>
  ```
- **Always re-trigger bugbot (Step 3 above) after pushing a fix**, regardless of which phase originated the findings. Any new commit invalidates bugbot's prior clean by definition, so bugbot must re-review the new HEAD before convergence can be claimed. Re-triggering in the same tick saves a full wakeup cycle compared to deferring the trigger to the next tick.

## Stop conditions

- **Convergence** (back-to-back clean as defined in Step 2 BUGTEAM second branch — `bugteam reports convergence AND bugbot_clean_at == current_head` with no push during this tick): mark PR ready for review, report one-sentence summary, omit ScheduleWakeup.
- **Hard blocker:** API auth failure persists across two ticks, a CI regression whose root cause falls outside this PR, a hook rejection investigated through three commits and still unresolved, `inline_lag_streak >= 3`, or `/bugteam` itself reports a stuck state. Report the specific blocker and the diagnosis, then omit ScheduleWakeup.
- **User stops the loop:** user says "stop the converge loop" → omit ScheduleWakeup on the next tick.
- **Safety cap:** `tick_count >= 30` (evaluated in Step 3.5) → omit ScheduleWakeup, report the cap was hit. See §Safety cap below for rationale.

## Safety cap

When `tick_count >= 30`, stop and report. That many rounds means something structural is wrong with the loop. (Higher than copilot-review's 20-tick cap because two reviewers run sequentially per round.) The increment lives in Step 1; the evaluation lives in Step 3.5.

## Ground rules

- **Append commits.** Each tick adds at most one new fix commit. Multiple findings within one tick collapse into a single commit; the next tick handles the next round.
- **`bugbot_clean_at` resets on every push.** A new commit invalidates bugbot's prior clean by definition — bugbot must re-review the new HEAD before convergence can be claimed.
- **Back-to-back clean is the ONLY termination criterion.** Convergence requires both reviewers clean against the same HEAD with no intervening fixes; either reviewer clean alone counts as in-progress.
- **The `bugbot run` comment is load-bearing.** Use the literal phrase `bugbot run` exactly — empirically the only re-trigger Cursor Bugbot recognizes; alternative phrasings silently no-op.
- **`gh pr ready` is the convergence action.** Mark the PR ready for review and stop there. Merge, additional reviewers, title, and body remain the user's decisions; the skill's contract ends at "ready for review."
- **Honor pre-push and pre-commit hooks.** When a hook rejects the change, read its output, fix the underlying issue (the failing test, the missing constant, the broken import), and retry.

## Examples

<example>
User: `/loop /pr-converge`
Claude: [reads PR context, runs one tick of bugbot phase, schedules next wakeup at 270s with prompt `/loop /pr-converge`, returns]
</example>

<example>
User: `/pr-converge`
Claude: [runs one tick manually, reports state, does NOT schedule a wakeup; user re-runs to advance]
</example>

<example>
Tick fires in BUGBOT phase, latest bugbot review is against an older commit.
Claude: [posts `bugbot run` comment, sets `bugbot_clean_at = null`, schedules next wakeup at 270s, returns]
</example>

<example>
Tick fires in BUGBOT phase, bugbot has 2 unaddressed findings on HEAD.
Claude: [TDD-fixes both, one commit, pushes, replies inline on both threads, posts `bugbot run`, schedules next wakeup at 270s, returns]
</example>

<example>
Tick fires in BUGBOT phase, bugbot is clean against HEAD.
Claude: [sets `bugbot_clean_at = HEAD`, transitions `phase = BUGTEAM`, runs `/bugteam` in the same tick]
</example>

<example>
In BUGTEAM phase, /bugteam reports convergence and `bugbot_clean_at == current_head`.
Claude: [runs `gh pr ready <NUMBER>`, reports "PR converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for review", omits ScheduleWakeup, terminates the /loop]
</example>

<example>
In BUGTEAM phase, /bugteam pushed a fix commit during its run.
Claude: [re-resolves HEAD, sets `bugbot_clean_at = null`, posts `bugbot run` in this same tick, transitions `phase = BUGBOT`, schedules next wakeup at 270s]
</example>

<example>
Tick fires in BUGBOT phase, bugbot review body says "found 3 potential issues" against HEAD but the inline-comments API returns zero matching comments for `current_head`.
Claude: [increments `inline_lag_streak` to 1, schedules next wakeup at 60s, returns; expects inline comments to appear by the next tick]
</example>
