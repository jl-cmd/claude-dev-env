---
name: autoconverge
description: >-
  Drives one draft PR to convergence in a single autonomous workflow run.
  Each round runs Cursor Bugbot, a code-review pass, and a bug-audit in
  parallel on the same HEAD, dedups findings, applies every fix in one
  commit, re-verifies, then clears a Copilot wait-gate and a closing
  convergence check before marking the PR ready. Use when the user says
  '/autoconverge', 'autoconverge this PR', 'converge this PR in one run',
  'run the converge workflow', or 'drive the PR to ready autonomously'.
---

# Autoconverge

One launch drives the whole loop to convergence. The `/autoconverge` skill
resolves PR scope, enters a worktree, grants project permissions, then hands
the loop to the **`converge.mjs` workflow**, which runs every round and every
reviewer wait inside one background pass — no ticks, no `ScheduleWakeup`, no
state file. State lives in the workflow's own variables; resume is handled by
the workflow journal.

`pr-converge` paces the same four-reviewer loop across `ScheduleWakeup` ticks;
autoconverge runs it as a deterministic workflow. The two skills share the same
helper scripts and the same convergence gate.

## Requirements

Scan the tool list at the top of this conversation for the literal string
`Workflow`. If it is absent, report `autoconverge requires the Workflow tool;
aborting` and stop. The workflow also needs the `gh` CLI authenticated for the
PR's owner.

## Pre-flight (main session)

1. **Enter a worktree.** Call `EnterWorktree` with no arguments before any
   `gh`, `git`, file read, or edit. `gh`/`git` Bash calls do not auto-isolate,
   so this is mandatory. If it fails, report and stop.

2. **Resolve PR scope.** When the user passed a PR URL or number, parse owner,
   repo, and number from it. Otherwise read the current branch's PR:
   `gh pr view --json number,headRefName,url,isDraft,baseRefName`. Capture
   `owner`, `repo`, `prNumber`. Confirm the PR is a draft; if it is already
   ready, mark it draft first (`gh pr ready <n> --repo <o>/<r> --undo`) so the
   loop owns the ready transition.

3. **Grant project permissions.**
   `python "$HOME/.claude/skills/bugteam/scripts/grant_project_claude_permissions.py"`

## Run the workflow

Call the `Workflow` tool against the colocated script:

```
Workflow({
  scriptPath: "<this skill dir>/workflow/converge.mjs",
  args: { owner: "<O>", repo: "<R>", prNumber: <N>, bugbotDisabled: false }
})
```

`scriptPath` is the absolute path to `workflow/converge.mjs` inside this skill's
own directory (on this install,
`<home>/.claude/skills/autoconverge/workflow/converge.mjs`). Set
`bugbotDisabled: true` only when the user has opted Cursor Bugbot out for the
run; otherwise the workflow detects an opt-out or an unreachable Bugbot on its
own. The workflow runs in the background and notifies this session on
completion. Watch live progress with `/workflows`.

The workflow returns
`{ converged, rounds, finalSha, blocker }`.

## Teardown (on workflow completion)

1. **When `converged` is true:** rewrite the PR description and clean the
   working tree — see
   [`bugteam/reference/teardown-publish-permissions.md` § Step 4 and § Step 4.5](../bugteam/reference/teardown-publish-permissions.md).
   The workflow already marked the PR ready.

2. **Always revoke project permissions** (including on a blocker exit):
   `python "$HOME/.claude/skills/bugteam/scripts/revoke_project_claude_permissions.py"`

3. **Print the final report:**

   ```
   /autoconverge exit: <converged | blocked>
   Rounds: <N>
   Final commit: <finalSha>
   Blocker: <blocker>        # only when blocked
   ```

## What the workflow does each round

See [`reference/convergence.md`](reference/convergence.md) for the full round
shape and the exact convergence definition, and
[`reference/stop-conditions.md`](reference/stop-conditions.md) for every way the
run ends short of ready. Hard-won failure lessons live in
[`reference/gotchas.md`](reference/gotchas.md).

- **Converge:** `parallel([Bugbot lens, code-review lens, bug-audit lens])` on
  the current HEAD, full `origin/main...HEAD` diff. Dedup findings; one
  `clean-coder` applies all fixes in a single commit, pushes, replies to and
  resolves any bot threads; re-verify next round on the new HEAD. When all
  three are clean on a stable HEAD, post the CLEAN bugteam audit artifact.
- **Copilot gate:** request a Copilot review, poll up to three times; findings
  route back into Converge, a no-show after the cap is a blocker.
- **Convergence check:** `check_convergence.py` is the authoritative gate; on a
  full pass the workflow marks `draft=false`.

## Folder map

- `SKILL.md` — this hub.
- `workflow/converge.mjs` — the convergence workflow script.
- `reference/` — convergence definition, stop conditions, gotchas.
