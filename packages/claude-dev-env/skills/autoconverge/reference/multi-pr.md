# Multiple PRs

The multi-PR run drives several draft PRs to ready in one launch:
`workflow/converge_multi.mjs` fans out one `converge.mjs` child run per PR with
`parallel()`, and every child is pinned to its own PR's worktree through the
`repoPath` it receives, so the children never share a checkout. Each child run is
the exact single-PR convergence loop — same rounds, same reuse pass, same Copilot
gate, same convergence check — one per PR at once. The children share the run's
concurrency cap, so the fan-out self-throttles rather than spawning every PR's
lenses at the same instant.

## Multi-PR pre-flight (main session)

`EnterWorktree` puts the session on one branch only, so the multi-PR path gives
each PR its own checkout with `git worktree add`. For each PR the user named:

1. **Resolve PR scope** as the single-PR pre-flight step 2 in
   [`SKILL.md`](../SKILL.md) does: capture `owner`, `repo`, `prNumber`, and
   `headRefName`; confirm the PR is a draft, and mark it draft
   (`gh pr ready <n> --repo <o>/<r> --undo`) when it is already ready so the
   loop owns the ready transition.
2. **Create a worktree on the PR's head ref** and capture its absolute path. From
   inside the PR's repository checkout:
   `git worktree add <abs worktree path> <headRefName>` (run `git fetch origin
   <headRefName>` first when the ref is not local). Put each PR's worktree under a
   path carrying its PR number so the fan-out keeps them distinct. Confirm
   `git -C <abs worktree path> rev-parse --abbrev-ref HEAD` equals the head ref
   and its `HEAD` equals the PR head SHA.
3. **Verify each worktree is the PR's repo (strict pre-flight):**
   `python "$HOME/.claude/skills/_shared/pr-loop/scripts/preflight_worktree.py" --owner <owner> --repo <repo> --mode strict`,
   run with that worktree as the working directory. A non-zero exit prints a
   `PREFLIGHT_OUTCOME` line and an `ABORT` line: report it and drop that PR from
   the run rather than aborting every PR.
4. **Grant project permissions once per repository** — the single-PR pre-flight
   step 4 grant covers every worktree of the same repo, so run it one time for
   the repo the PRs live in.
5. **Copilot quota pre-check once for the whole run** — run the single-PR
   pre-flight step 5 check one time:
   `python "$HOME/.claude/skills/_shared/pr-loop/scripts/copilot_quota.py"`. Every PR in
   the run shares one account's Copilot premium-request quota, so one check covers
   them all. Exit 0 sets `copilotDisabled: false` on every PR entry below; any
   non-zero exit sets `copilotDisabled: true` on every entry, so each child skips
   the Copilot gate with no agent spawned.

## Launch

Select the pacer once for the multi-PR run (same helper as single-PR):

```
python "$HOME/.claude/skills/_shared/pr-loop/scripts/select_converge_pacer.py" \
  --skill autoconverge \
  --has-workflow <0|1> \
  --has-schedule-wakeup <0|1>
```

### `pacer=portable`

Do **not** call `Workflow`. For each PR worktree from pre-flight, run the
continuous portable driver in
[`../../_shared/pr-loop/portable-driver.md`](../../_shared/pr-loop/portable-driver.md)
(serial, or host fan-out when the host can isolate workers). One teardown per
PR after that PR reaches ready or a named blocker. Shared Copilot quota and
permission grants from multi-PR pre-flight still apply once.

### `pacer=workflow`

Call the `Workflow` tool against the fan-out script, passing the absolute path of
`converge.mjs` and one entry per PR:

```
Workflow({
  scriptPath: "<this skill dir>/workflow/converge_multi.mjs",
  args: {
    convergeScriptPath: "<this skill dir>/workflow/converge.mjs",
    homeDirectory: "<HOME>",
    prs: [
      { owner: "<O>", repo: "<R>", prNumber: <N1>, repoPath: "<abs worktree 1>", bugbotDisabled: false, copilotDisabled: false },
      { owner: "<O>", repo: "<R>", prNumber: <N2>, repoPath: "<abs worktree 2>", bugbotDisabled: false, copilotDisabled: false }
    ]
  }
})
```

`convergeScriptPath` is the absolute path to `workflow/converge.mjs` in this same
skill directory; each `repoPath` is the absolute path of the worktree that PR is
checked out in. `homeDirectory` is the absolute path to the directory that holds
`.claude` (resolve it once from `$HOME`, or `$env:USERPROFILE` on Windows, with
forward slashes); the fan-out forwards it to every child run, which needs it to
build the codex-review scripts path because the workflow sandbox has no access to
environment variables. The workflow runs in the background and notifies the session on
completion; watch live progress with `/workflows`, where each PR's child run
appears under its own group.

The workflow returns
`{ converged, prCount, convergedCount, results, allDeferredPrs, blocker }`, where
`results` is one record per PR carrying
`{ owner, repo, prNumber, converged, rounds, finalSha, blocker, deferredPrs }`.
Each record's `deferredPrs` is that PR's own list of draft hardening PRs, and
`allDeferredPrs` is every record's `deferredPrs` flattened into one list. The
top-level `converged` is true only when every PR converged.

## Multi-PR teardown

### `pacer=portable`

For each PR worktree, run the single-PR **Teardown → pacer=portable** path in
[`SKILL.md`](../SKILL.md) (`pr-loop-lifecycle` Close, no Workflow journal
report). Write one durable handoff per PR with that PR's `--pr-number` and
resume command `/autoconverge <PR URL>`. Revoke project permissions once per
repository after every PR's close. Print one summary line per PR as
`#<prNumber>: <converged | blocked> — rounds <N>, final <finalSha>[, blocker <blocker>]`.

### `pacer=workflow` (on workflow completion)

Run the single-PR Teardown in [`SKILL.md`](../SKILL.md) once per entry in
`results`, using that PR's `owner`, `repo`, `prNumber`, and `finalSha`, and its
own worktree as the working directory. Write one durable handoff per PR entry —
each with that PR's own `--pr-number` — so a fresh session can resume any PR on
its own. Build and publish a PR's closing report
only for a PR whose `converged` is true; for a PR that returned a blocker, skip
its report and carry the blocker into the final summary. Revoke project
permissions once per repository after every PR's teardown. Then print one summary
report — a line per PR as
`#<prNumber>: <converged | blocked> — rounds <N>, final <finalSha>[, blocker <blocker>]`.
