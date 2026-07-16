# Copilot-review subagent prompt template

The background watcher prompt for the `copilot-review` skill. The hub
([`../SKILL.md`](../SKILL.md) Step 3) passes the fenced block below to the
subagent word for word, with the bracketed values ([NUMBER], [OWNER], [REPO],
[BRANCH], [HEAD_SHA]) filled in from Step 1.

```text
You are babysitting the GitHub Copilot reviewer on PR **#[NUMBER]** at **[OWNER]/[REPO]** (branch `[BRANCH]`, current HEAD `[HEAD_SHA]`). Your job: keep the loop running until Copilot returns a clean review against the current HEAD, then stop.

**Per-tick work** (do this now, then on each wakeup):

1. Resolve current HEAD: `pull_request_read(method="get", pullNumber=[NUMBER], owner="[OWNER]", repo="[REPO]")` and extract `.head.sha`.
2. Fetch latest Copilot review via `pull_request_read(method="get_reviews", pullNumber=[NUMBER], owner="[OWNER]", repo="[REPO]")`.
   Capture `commit_id`, `state`, `submitted_at`, `id`.
3. Decide the branch:
   - **No review exists:** increment `no_review_count` (see escalation rule below), re-request (step 4), schedule next wakeup, return.
   - **Latest review's `commit_id` != current HEAD:** increment `no_review_count`, re-request (step 4), schedule next wakeup, return.
   - **Latest review's `commit_id` == current HEAD with unresolved inline findings:** reset `no_review_count` to 0, TDD-fix them, push, reply inline on each thread, resolve each addressed thread, re-request (step 4), schedule next wakeup, return.
   - **Latest review's `commit_id` == current HEAD and clean:** report convergence to the parent with a one-sentence summary and terminate. The loop is done; skip the ScheduleWakeup call.

   **Escalation rule:** `no_review_count` starts at 0, counts consecutive ticks where no Copilot review exists at the current HEAD, and resets to 0 on every push and every review sighted at HEAD. When it reaches 3, Copilot is not delivering reviews — report the stall to the parent with the count and the last request timestamp, then terminate without scheduling another wakeup.
4. Re-request Copilot via `request_copilot_review(owner="[OWNER]", repo="[REPO]", pullNumber=[NUMBER])`.
   The reviewer ID **must** be `copilot-pull-request-reviewer[bot]` with the `[bot]` suffix — empirically verified: `Copilot`, `copilot`, and `github-copilot` all return `requested_reviewers: []` with no error, silently no-op.
5. Schedule the next wakeup with `ScheduleWakeup`:
   - `delaySeconds: 360`
   - `reason`: one short sentence on what you are waiting for.
   - `prompt`: the literal sentinel `<<autonomous-loop-dynamic>>` so the next firing re-enters these instructions.

**Fix protocol** (step 3, third branch):

- Read `$HOME/.claude/skills/pr-fix-protocol/SKILL.md` and apply it — it carries the shared fix sequence, the reply-and-resolve unit, and the unresolved-thread sweep.
- Read each referenced file:line.
- Write a failing test first when the finding has behavior to test. For pure doc or comment nits that have no behavior, go straight to the fix.
- Stage the fix and create one new commit on the existing branch: `git add <files> && git commit -m "fix(review): ..."`.
- Push the new commit: `git push origin [BRANCH]`.
- Reply inline via `add_reply_to_pull_request_comment(owner="[OWNER]", repo="[REPO]", pullNumber=[NUMBER], body="...", commentId=<comment_id>)`, referencing the new commit SHA; then resolve each addressed thread via `pull_request_review_write(method="resolve_thread", pullNumber=[NUMBER], owner="[OWNER]", repo="[REPO]", threadId="<PRRT id>")`, harvesting the `PRRT_…` id from `pull_request_read(method="get_review_comments", ...)`. Reply first, then resolve — atomic per thread, per the protocol.

When a pre-push, pre-commit, or other hook rejects the change, solve it. Read the hook's error message, diagnose the root cause in the code or test, and fix that. Then rerun the commit or push. Hooks exist to catch real problems; treat each rejection as new evidence to act on.

**Stop conditions:**

- Convergence (clean review against HEAD): report one-sentence summary to parent and terminate.
- Blocker you have exhausted fix attempts on (API auth failure persists, CI regression whose root cause falls outside this PR, a hook you have investigated and cannot resolve in one commit): report the specific blocker and its diagnosis to the parent, then terminate without scheduling another wakeup.
- Parent sends `TaskStop`: terminate immediately.
- `no_review_count` reaches 3 (escalation rule above): report the stall and terminate.

**Safety cap:** after 20 ticks without convergence, stop and report. This is the total-tick runaway guard, distinct from the 3-consecutive-no-review escalation; that many rounds means something structural is wrong with the loop.
```
