---
name: copilot-review
description: >-
  Spawns a background subagent that babysits the GitHub Copilot reviewer on the
  current PR: each tick it fixes unaddressed findings against HEAD, re-requests
  review, and exits on convergence. Triggers: '/copilot-review', 'watch
  copilot', 'babysit copilot review', 'keep re-requesting copilot'.
---

# Copilot Review

Delegates Copilot babysitting to a background subagent so the main session stays free. The subagent loops internally and closes itself on convergence.

## Transport check (before any GitHub step)

Run `command -v gh`; when it succeeds, run `gh auth status`; once the PR scope is resolved, run `gh api repos/<owner>/<repo> --jq .permissions.push` and take `true` as the pass. When any check fails, run the `pr-loop-cloud-transport` skill first, route every `gh` operation in this skill through its substitution matrix, and carry the same routing into the subagent prompt so the spawned watcher inherits it.

## When this skill applies

The user is on a PR branch, wants Copilot (the GitHub Copilot reviewer bot) to keep re-reviewing after each push, and wants findings auto-addressed between ticks — but does not want the main conversation consumed by polling.

## The Process

### Step 0: Opt-out check

Before any other work, run:

```bash
python "$HOME/.claude/skills/_shared/pr-loop/scripts/reviews_disabled.py" --reviewer copilot
```

Exit 0 — Copilot reviews are disabled: respond with the literal line
`/copilot-review is disabled via CLAUDE_REVIEWS_DISABLED.` and stop — do not
spawn the subagent, do not call the Copilot reviewer API, do not run any
other step of this skill. Exit 1 — continue. Gate semantics live in the
`reviewer-gates` skill ([../reviewer-gates/SKILL.md](../reviewer-gates/SKILL.md)).

### Step 1: Gather PR context

From the current repo:

```bash
# MCP: pull_request_read(method="get") returns {number, url, head.sha, base.ref, head.ref, isDraft}
```

Capture `number`, `head.sha`, owner/repo (from `url`), and branch name. Pass these to the subagent so it does not rediscover them.

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

Pass the prompt in
[`templates/subagent-prompt.md`](templates/subagent-prompt.md) to the subagent
word for word, filling in the bracketed values ([NUMBER], [OWNER], [REPO],
[BRANCH], [HEAD_SHA]) from Step 1. It carries the per-tick work, the escalation
rule (three consecutive no-review ticks), the fix protocol, the stop conditions,
and the 20-tick safety cap.

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
Subagent: [TDD-fixes both, one commit, pushes, replies inline on both threads, resolves both threads, re-requests review, schedules next wakeup]
</example>

<example>
Subagent tick fires, latest review is clean against HEAD.
Subagent: [reports convergence to parent, terminates — no further wakeups]
</example>
