---
name: copilot-review
description: >-
  Spawns a background subagent that babysits the GitHub Copilot reviewer on the
  current PR. The subagent self-paces at ~5 minutes per tick, fetches the
  latest copilot-pull-request-reviewer[bot] review, fixes unaddressed inline
  findings against current HEAD (new commit, push, inline replies), and
  re-requests review via the documented requested_reviewers API. The subagent
  terminates on convergence (clean review against HEAD) and reports back.
  Triggers: '/copilot-review', 'watch copilot', 'babysit copilot review',
  'loop copilot reviews', 're-request copilot', 'keep re-requesting copilot'.
---

# Copilot Review

Delegates Copilot babysitting to a background subagent so the main session stays free. The subagent loops internally and closes itself on convergence.

## When this skill applies

The user is on a PR branch, wants Copilot (the GitHub Copilot reviewer bot) to keep re-reviewing after each push, and wants findings auto-addressed between ticks — but does not want the main conversation consumed by polling.

## The Process

### Step 1: Gather PR context

From the current repo:

```bash
gh pr view --json number,url,headRefOid,baseRefName,headRefName,isDraft
```

Capture `number`, `headRefOid`, owner/repo (from `url`), and branch name. Pass these to the subagent so it does not rediscover them.

### Step 2: Spawn the background subagent

Invoke the `Agent` tool with:

- `subagent_type: "general-purpose"`
- `run_in_background: true`
- `description: "Copilot review loop for PR #<N>"`
- `prompt`: the full instructions in **Step 3 (Subagent prompt template)**, with placeholders filled in from Step 1.

Record the returned agent ID. Report to the user in one or two lines:

- The subagent is running in the background.
- It self-terminates on convergence.
- To stop it early, the user says "stop the copilot loop" and you call `TaskStop <agent_id>`.
- The main session stays free; completion arrives as a notification.

Let the subagent own the cadence. The skill's job in the main session ends once the subagent is spawned and reported.

### Step 3: Subagent prompt template

Pass this verbatim to the subagent (substituting the bracketed values):

> You are babysitting the GitHub Copilot reviewer on PR **#[NUMBER]** at **[OWNER]/[REPO]** (branch `[BRANCH]`, current HEAD `[HEAD_SHA]`). Your job: keep the loop running until Copilot returns a clean review against the current HEAD, then stop.
>
> **Per-tick work** (do this now, then on each wakeup):
>
> 1. Resolve current HEAD: `gh api repos/[OWNER]/[REPO]/pulls/[NUMBER] --jq '.head.sha'`.
> 2. Fetch latest Copilot review:
>    ```bash
>    gh api repos/[OWNER]/[REPO]/pulls/[NUMBER]/reviews \
>      --jq '[.[] | select(.user.login=="copilot-pull-request-reviewer[bot]")] | sort_by(.submitted_at) | last'
>    ```
>    Capture `commit_id`, `state`, `submitted_at`, `id`.
> 3. Decide the branch:
>    - **No review exists:** re-request (step 4), schedule next wakeup, return.
>    - **Latest review's `commit_id` != current HEAD:** re-request (step 4), schedule next wakeup, return.
>    - **Latest review's `commit_id` == current HEAD with unresolved inline findings:** TDD-fix them, push, reply inline on each thread, re-request (step 4), schedule next wakeup, return.
>    - **Latest review's `commit_id` == current HEAD and clean:** report convergence to the parent with a one-sentence summary and terminate. The loop is done; skip the ScheduleWakeup call.
> 4. Re-request Copilot. The reviewer ID **must** be `copilot-pull-request-reviewer[bot]` with the `[bot]` suffix — empirically verified: `Copilot`, `copilot`, and `github-copilot` all return `requested_reviewers: []` with no error, silently no-op.
>    ```bash
>    gh api -X POST repos/[OWNER]/[REPO]/pulls/[NUMBER]/requested_reviewers \
>      -f 'reviewers[]=copilot-pull-request-reviewer[bot]'
>    ```
> 5. Schedule the next wakeup with `ScheduleWakeup`:
>    - `delaySeconds: 300`
>    - `reason`: one short sentence on what you are waiting for.
>    - `prompt`: the literal sentinel `<<autonomous-loop-dynamic>>` so the next firing re-enters these instructions.
>
> **Fix protocol** (step 3, third branch):
>
> - Read each referenced file:line.
> - Write a failing test first when the finding has behavior to test. For pure doc or comment nits that have no behavior, go straight to the fix.
> - Implement the fix.
> - Stage the fix and create one new commit on the existing branch: `git add <files> && git commit -m "fix(review): ..."`.
> - Push the new commit: `git push origin [BRANCH]`.
> - Reply inline on each comment thread with `gh api -X POST repos/[OWNER]/[REPO]/pulls/[NUMBER]/comments` using `in_reply_to` set to the comment id, referencing the new commit SHA.
>
> When a pre-push, pre-commit, or other hook rejects the change, solve it. Read the hook's error message, diagnose the root cause in the code or test, and fix that. Then rerun the commit or push. Hooks exist to catch real problems; treat each rejection as new evidence to act on.
>
> **Stop conditions:**
>
> - Convergence (clean review against HEAD): report one-sentence summary to parent and terminate.
> - Blocker you have exhausted fix attempts on (API auth failure persists, CI regression whose root cause falls outside this PR, a hook you have investigated and cannot resolve in one commit): report the specific blocker and its diagnosis to the parent, then terminate without scheduling another wakeup.
> - Parent sends `TaskStop`: terminate immediately.
>
> **Safety cap:** after 20 ticks without convergence, stop and report. That many rounds means something structural is wrong with the loop.

### Step 4: Report back to the user

After spawning, tell the user in one or two lines: subagent ID, PR URL, that it will notify on convergence or blocker. Nothing else.

## Stopping the subagent

- Convergence → subagent stops itself.
- Blocker → subagent reports and stops.
- User says stop → `TaskStop <agent_id>`.
- User asks what loops are running → `TaskList`.

## Ground rules (for the subagent)

- **Append commits.** Each tick adds one new commit on the existing branch with `git commit` and `git push origin [BRANCH]`.
- **Honor pre-push and pre-commit hooks.** When a hook rejects the change, read its output, fix the underlying issue (the failing test, the missing constant, the broken import), and retry. Solve, do not punt.
- **Respect the PR's current state.** Whatever draft-vs-ready state the PR has when the loop starts is the state the subagent preserves. The user decides when to flip it.
- **One fix commit per tick.** Batch all of the current tick's findings into a single commit; the next tick handles the next review round.
- **Use `copilot-pull-request-reviewer[bot]` with the `[bot]` suffix for the reviewer ID.** That exact spelling is load-bearing — it is the only form the API accepts.

## Examples

<example>
User: `/copilot-review`
Claude: [reads PR context, spawns background subagent with the Step 3 template, reports "subagent X watching PR #123; will notify on convergence"]
</example>

<example>
User: "babysit copilot on this PR until it's clean"
Claude: [same as above]
</example>

<example>
Subagent tick fires, latest Copilot review is against an older commit.
Subagent: [re-requests review, schedules next wakeup, returns]
</example>

<example>
Subagent tick fires, Copilot has 2 unaddressed inline findings on HEAD.
Subagent: [TDD-fixes both, one commit, pushes, replies inline on both threads, re-requests review, schedules next wakeup]
</example>

<example>
Subagent tick fires, latest review is clean against HEAD.
Subagent: [reports convergence to parent, terminates — no further wakeups]
</example>
