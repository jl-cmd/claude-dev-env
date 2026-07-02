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

## Run scope: one PR or several

Decide the scope from how many PRs the user named, then follow that path:

1. **One PR** → the single-PR run described below (`workflow/converge.mjs`): one
   worktree, one workflow launch, one teardown.
2. **Several PRs** → the [Multiple PRs](#multiple-prs) run
   (`workflow/converge_multi.mjs`): one worktree per PR and a single workflow
   launch that drives every PR's converge run in parallel, then one teardown per
   PR.

The single-PR sections (Requirements, Pre-flight, Run the workflow, Teardown)
each describe one converge run. The Multiple PRs section reuses them once per PR
and adds only what fanning out needs: a per-PR worktree and a per-PR teardown
loop.

## Requirements

Scan the tool list at the top of this conversation for the literal string
`Workflow`. If it is absent, report `autoconverge requires the Workflow tool;
aborting` and stop. The workflow also needs the `gh` CLI authenticated for the
PR's owner.

## Pre-flight (main session)

1. **Enter a worktree.** Call `EnterWorktree` with no arguments before any
   `gh`, `git`, file read, or edit. `gh`/`git` Bash calls do not auto-isolate,
   so this is mandatory. If it fails, report and stop. A bare `EnterWorktree`
   branches from `origin/main`; step 2 positions the worktree on the PR's head
   ref, which the workflow needs.

2. **Resolve PR scope.** When the user passed a PR URL or number, parse owner,
   repo, and number from it. Otherwise read the current branch's PR:
   `gh pr view --json number,headRefName,url,isDraft,baseRefName`. Capture
   `owner`, `repo`, `prNumber`. Confirm the PR is a draft; if it is already
   ready, mark it draft first (`gh pr ready <n> --repo <o>/<r> --undo`) so the
   loop owns the ready transition.

   **Position the worktree on the PR branch.** The workflow reviews
   `git diff origin/main...HEAD` against this worktree's local `HEAD` and pushes
   each fix to the PR branch, so the worktree sits on the PR's head ref at the PR
   HEAD before the workflow launches. A worktree fresh off `origin/main` has
   `HEAD == origin/main`, shows an empty diff, and reports a false convergence
   with zero findings. When a local worktree already tracks the PR branch, enter
   that one by passing its path to `EnterWorktree`; otherwise put the entered
   worktree on the branch with `gh pr checkout <number> --repo <owner>/<repo>`
   (or `git fetch origin <headRefName>` then `git switch <headRefName>`). Confirm
   before launching: `git rev-parse --abbrev-ref HEAD` equals the PR's head ref
   and local `HEAD` equals the PR head SHA.

3. **Verify the worktree is the PR's repo (strict pre-flight).** Run
   `python "$HOME/.claude/skills/_shared/pr-loop/scripts/preflight_worktree.py" --owner <owner> --repo <repo> --mode strict`.
   It confirms the working directory is a checkout of the PR's own repo and
   that `git worktree` machinery is healthy, so `EnterWorktree` can create and
   enter the branch worktree. A non-zero exit prints a `PREFLIGHT_OUTCOME` line
   and an `ABORT` line: report that line and stop. Autoconverge runs inside the
   PR's own repo, so a working directory rooted in a different repo (for
   example, `claude-code-config` while the PR lives in `llm-settings`) or in no
   git checkout at all cannot continue.

4. **Grant project permissions.**
   `python "$HOME/.claude/skills/bugteam/scripts/grant_project_claude_permissions.py"`

   In auto-mode the classifier blocks this grant as an unrequested change to the
   permission allowlist: the `/autoconverge` invocation alone does not meet its
   bar for an explicitly requested permission change. When it is blocked, keep
   the run alive — surface the grant to the user through `AskUserQuestion` with
   the exact command and ask them to approve it or run it themselves with the `!`
   prefix:
   `! python "$HOME/.claude/skills/bugteam/scripts/grant_project_claude_permissions.py"`.
   Continue once the grant lands. A user who wants future runs to skip this
   prompt can add a standing Bash permission allow-rule for that script in their
   settings.

5. **Copilot quota pre-check.** Before the `Workflow` call, run once:
   `python "$HOME/.claude/_shared/pr-loop/scripts/copilot_quota.py"`
   It reads the account's remaining Copilot premium-request quota via
   `gh api copilot_internal/user` and prints one line — log that line. Exit 0
   means Copilot has quota to run, so pass `copilotDisabled: false`. Any non-zero
   exit means skip Copilot for this run — the account is out of quota, the quota
   API or account access is down, or no account is set — so pass
   `copilotDisabled: true`; the workflow then skips the Copilot gate with no agent
   spawned. The account comes from the `COPILOT_QUOTA_ACCOUNT` environment
   variable or a git-ignored `.env` file, and the no-account line names the exact
   `.env` path and key to set.

## Run the workflow

Call the `Workflow` tool against the colocated script:

```
Workflow({
  scriptPath: "<this skill dir>/workflow/converge.mjs",
  args: { owner: "<O>", repo: "<R>", prNumber: <N>, bugbotDisabled: false, copilotDisabled: false }
})
```

`scriptPath` is the absolute path to `workflow/converge.mjs` inside this skill's
own directory (on this install,
`<home>/.claude/skills/autoconverge/workflow/converge.mjs`). Set
`bugbotDisabled: true` only when the user has opted Cursor Bugbot out for the
run; otherwise the workflow detects an opt-out or an unreachable Bugbot on its
own. Set `copilotDisabled: true` when the step 5 quota pre-check exits non-zero,
and `false` when it exits 0; on `true` the workflow skips the Copilot gate with
no agent spawned. The workflow runs in the background and notifies this session
on completion. Watch live progress with `/workflows`.

The workflow returns
`{ converged, rounds, finalSha, blocker, standardsNote, copilotNote, reuseNote }`.

## Budget-aware round boundaries

The workflow's `budget` API is the pacing signal: when a usage target is
set, `converge.mjs` checks `budget.remaining()` before each round and
stops at the round boundary when one full round (three parallel lenses +
one fix commit + re-verify) does not fit. On a budget stop the workflow
returns `blocker: "budget"` with the run id; resume with
`Workflow({scriptPath, resumeFromRunId})` — completed rounds replay from
the journal. Never start a round the budget cannot finish: a half-run
round records nothing resumable and replays dirty.

## Teardown (on workflow completion)

1. **When `converged` is true — build and publish the closing report.**
   Skip this entire step (report, gist, comment, Chrome open) when the workflow
   returned a non-null `blocker`. Per-round live-dashboard refresh is out of scope
   here; this step builds the one-shot closing report and the seam (marker comment +
   gist URL) a future live-dashboard reuses.

   a. **Resolve a seed journal path.** Glob
      `~/.claude/projects/**/workflows/wf_<runId>.json` (where `runId` is the run id
      the `Workflow` result returned) and take the match. It seeds the merge, which
      finds every other autoconverge journal for the same PR.

   b. **Merge the PR's runs and build the summary prompt.**
      ```
      python "<skill>/workflow/aggregate_runs.py" \
        --journal "<seed journal>" \
        --pr <owner>/<repo>#<n> \
        --work-dir "$CLAUDE_JOB_DIR/tmp/autoconverge-agg-<prNumber>" \
        --out-prompt "$CLAUDE_JOB_DIR/tmp/autoconverge-summary-prompt-<prNumber>.txt" \
        [--standards-note "<standardsNote>"] [--copilot-note "<copilotNote>"]
      ```
      It prints a JSON line with `combinedJournal`, `roundCount`, `finalSha`, and
      `findingCount`. Pass `--standards-note`/`--copilot-note` only when the workflow
      returned those notes.

   c. **Write the summary.** Spawn a `convergence-summary` agent (a `general-purpose`
      subagent) on the text of the prompt file from step b. The agent answers with the
      `prProblem`/`prFix`/`problemScenes`/`fixScenes`/`verdictLine`/`issueClasses` JSON
      object; write that object to
      `$CLAUDE_JOB_DIR/tmp/autoconverge-summary-<prNumber>.json`.

   d. **Build the report.**
      ```
      python "<skill>/workflow/render_report.py" \
        --journal "<combinedJournal>" \
        --summary-file "<summary json>" \
        --out "$CLAUDE_JOB_DIR/tmp/autoconverge-report-<prNumber>.html" \
        --pr <owner>/<repo>#<n> \
        --final-sha <finalSha> \
        --rounds <roundCount>
      ```
      Use the `combinedJournal`, `finalSha`, and `roundCount` from step b. Capture the
      output path from stdout.

   e. **Publish as a secret gist** by reusing `doc-gist` (do not reimplement gist
      creation):
      ```
      python "$HOME/.claude/skills/doc-gist/scripts/gist_upload.py" \
        --input "<html path>" \
        --no-open \
        --description "autoconverge report PR #<n>"
      ```
      Capture the htmlpreview URL from stdout. The gist is secret by default; pass
      no public flag.

   f. **Post one idempotent PR comment.** List the PR's issue comments; if one
      carries the marker `<!-- autoconverge-report -->`, edit it in place, otherwise
      create a new one. The body begins with `<!-- autoconverge-report -->`, then
      the htmlpreview link, then a plain-language summary that mirrors the report:
      lead with the one-sentence `verdictLine`; then the plain Problem and Fix
      sentences (`prProblem`, `prFix`); then the issue-class list — one bullet per
      class as `plainName (×count, status)`. Place the raw finding list as
      `file:line — P# — title` inside a collapsed
      `<details><summary>Raw findings</summary>…</details>` block so the comment leads
      with the human summary. Honor the gh-body-file rule: write a BOM-free temp file
      and pass `--body-file` to `gh issue comment`/`gh issue comment edit`, or use the
      GitHub MCP `add_issue_comment` tool (body as a structured parameter, no
      `--body` flag).

   g. **Open the report in Chrome.**
      ```
      Start-Process chrome -ArgumentList '--new-window', '<report path>'
      ```
      Tolerate a missing Chrome without aborting the rest of teardown.

2. **When `converged` is true:** rewrite the PR description and clean the
   working tree — see
   [`bugteam/reference/teardown-publish-permissions.md` § Step 4 and § Step 4.5](../bugteam/reference/teardown-publish-permissions.md).
   The workflow already marked the PR ready.

3. **Always revoke project permissions** (including on a blocker exit):
   `python "$HOME/.claude/skills/bugteam/scripts/revoke_project_claude_permissions.py"`

4. **Print the final report:**

   ```
   /autoconverge exit: <converged | blocked>
   Rounds: <N>
   Final commit: <finalSha>
   Blocker: <blocker>        # only when blocked
   Standards: <standardsNote> # only when a round deferred code-standard findings
   Copilot: <copilotNote>     # only when Copilot was down or out of quota
   Reuse: <reuseNote>         # only when the reuse pass identified an improvement
   ```

## Reuse pass (before convergence)

Before the first round, one reuse lens (`code-quality-agent`) scans the full
`origin/main...HEAD` diff for places the PR re-implements behavior the codebase
already provides. It reports a reuse improvement only when all three criteria
hold, and drops any case where even one is in doubt:

- **Certain** — an existing symbol or module unquestionably covers the new
  code's behavior, cited at `file:line`.
- **Behaviorally identical** — swapping the new code for the existing one
  changes no observable behavior: same inputs, outputs, side effects, and error
  handling.
- **Autonomously implementable** — the replacement is a mechanical edit (import
  and call the existing symbol, delete the duplicate) needing no product
  decision and no human judgment.

The reuse lens reports without editing. Qualifying improvements then run through
the same edit → verify → commit fix flow the rounds use, so they land in one
verified commit before convergence starts. The pass is best-effort: when no case
clears all three criteria, the run proceeds straight to convergence, and
`reuseNote` records what landed.

## What the workflow does each round

See [`reference/convergence.md`](reference/convergence.md) for the full round
shape and the exact convergence definition, and
[`reference/stop-conditions.md`](reference/stop-conditions.md) for every way the
run ends short of ready. Hard-won failure lessons live in
[`reference/gotchas.md`](reference/gotchas.md).

Every agent prompt carries a headless-safety preamble: the run is unattended, so
agents never inline a destructive-command literal (`rm -rf`, `git reset --hard`,
`dd`) into a Bash command — the `destructive_command_blocker` hook matches those
patterns as raw text, and a confirmation prompt no human can answer would stall
the run. Agents verify destructive-blocker behavior through the committed test
suite (`python -m pytest`) and keep scratch work in the OS temp dir. The preamble
describes the narrowest rm auto-allow path — a standalone Bash call whose target
resolves inside the ephemeral namespace (`/tmp`, `/temp`, the OS temp root, or the
run worktree) — and a compound path that accepts an rm joined with benign
reporting segments when every rm target is an absolute ephemeral path. Both of
those paths fail closed on `$(...)` substitution and backtick subshells. The
compound path also fails closed on any `$` in the target — including
`$CLAUDE_JOB_DIR`. The standalone path declines a `$`-bearing target only when
the literal path is not already under an ephemeral root, so it does not by
itself stop a `$VAR` that expands inside an ephemeral root. A third, broad path
matches only when the command itself declares an
ephemeral working directory (it `cd`s into one, or runs under one): that
cwd-scoped path resolves the target against the declared cwd, fails closed on
`$(...)`, backticks, and unknown variables, and resolves the known temporary
variables `TEMP`, `TMP`, `TMPDIR`, and `CLAUDE_JOB_DIR` to the OS temp root, so
under that declared ephemeral cwd a bare `$CLAUDE_JOB_DIR/tmp/<name>` target and a
relative target after a `cd` are auto-allowed. Even so, for any cleanup whose path
is variable-built or whose teardown spans multiple steps, agents author a Python
helper file and run it as `python <file>.py` — keeping every destructive literal
out of a Bash command string entirely and independent of which auto-allow path
matches.

- **Converge:** `parallel([Bugbot lens, code-review lens, bug-audit lens])` on
  the current HEAD, full `origin/main...HEAD` diff. Dedup findings; one
  `clean-coder` applies all fixes in a single commit, pushes, replies to and
  resolves any bot threads; re-verify next round on the new HEAD. Every edit
  step ends with a pre-commit gate check: before its turn ends, the fixer
  dry-runs the CODE_RULES commit gate (`code_rules_gate.py --staged`) and keeps
  fixing until that gate would accept the commit — it makes no commit itself.
  When all three are clean on a stable HEAD, post the CLEAN bugteam audit
  artifact.
  A round whose findings are ALL code-standard violations (pure CODE_RULES/style,
  no behavioral impact) passes for convergence purposes: the workflow files a
  follow-up issue listing the findings, opens a draft environment-hardening PR
  (hooks/rules that block those violation classes at Write/Edit time), resolves
  any bot threads with a deferral note, and reports the deferral in
  `standardsNote`.
- **Copilot gate:** request a Copilot review, poll up to the configured cap; findings
  route back into Converge. When Copilot is down or out of quota — it posts an
  out-of-usage notice (the requester hit their quota) on the HEAD, or surfaces no
  review at all after the configured cap — the gate logs a notice and the run marks the PR
  ready with the Copilot gate bypassed. `copilotNote` records the bypass.
- **Convergence check:** `check_convergence.py` is the authoritative gate; on a
  full pass the workflow marks `draft=false`.

## Multiple PRs

The multi-PR run drives several draft PRs to ready in one launch:
`workflow/converge_multi.mjs` fans out one `converge.mjs` child run per PR with
`parallel()`, and every child is pinned to its own PR's worktree through the
`repoPath` it receives, so the children never share a checkout. Each child run is
the exact single-PR convergence loop — same rounds, same reuse pass, same Copilot
gate, same convergence check — one per PR at once. The children share the run's
concurrency cap, so the fan-out self-throttles rather than spawning every PR's
lenses at the same instant.

### Multi-PR pre-flight (main session)

`EnterWorktree` puts the session on one branch only, so the multi-PR path gives
each PR its own checkout with `git worktree add`. For each PR the user named:

1. **Resolve PR scope** as the single-PR pre-flight step 2 does: capture `owner`,
   `repo`, `prNumber`, and `headRefName`; confirm the PR is a draft, and mark it
   draft (`gh pr ready <n> --repo <o>/<r> --undo`) when it is already ready so the
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
   `python "$HOME/.claude/_shared/pr-loop/scripts/copilot_quota.py"`. Every PR in
   the run shares one account's Copilot premium-request quota, so one check covers
   them all. Exit 0 sets `copilotDisabled: false` on every PR entry below; any
   non-zero exit sets `copilotDisabled: true` on every entry, so each child skips
   the Copilot gate with no agent spawned.

### Launch the multi-PR workflow

Call the `Workflow` tool against the fan-out script, passing the absolute path of
`converge.mjs` and one entry per PR:

```
Workflow({
  scriptPath: "<this skill dir>/workflow/converge_multi.mjs",
  args: {
    convergeScriptPath: "<this skill dir>/workflow/converge.mjs",
    prs: [
      { owner: "<O>", repo: "<R>", prNumber: <N1>, repoPath: "<abs worktree 1>", bugbotDisabled: false, copilotDisabled: false },
      { owner: "<O>", repo: "<R>", prNumber: <N2>, repoPath: "<abs worktree 2>", bugbotDisabled: false, copilotDisabled: false }
    ]
  }
})
```

`convergeScriptPath` is the absolute path to `workflow/converge.mjs` in this same
skill directory; each `repoPath` is the absolute path of the worktree that PR is
checked out in. The workflow runs in the background and notifies this session on
completion; watch live progress with `/workflows`, where each PR's child run
appears under its own group.

The workflow returns `{ converged, prCount, convergedCount, results, blocker }`,
where `results` is one record per PR carrying
`{ owner, repo, prNumber, converged, rounds, finalSha, blocker }`. The top-level
`converged` is true only when every PR converged.

### Multi-PR teardown (on workflow completion)

Run the single-PR [Teardown](#teardown-on-workflow-completion) once per entry in
`results`, using that PR's `owner`, `repo`, `prNumber`, and `finalSha`, and its
own worktree as the working directory. Build and publish a PR's closing report
only for a PR whose `converged` is true; for a PR that returned a blocker, skip
its report and carry the blocker into the final summary. Revoke project
permissions once per repository after every PR's teardown. Then print one summary
report — a line per PR as
`#<prNumber>: <converged | blocked> — rounds <N>, final <finalSha>[, blocker <blocker>]`.

## Folder map

- `SKILL.md` — this hub.
- `workflow/converge.mjs` — the convergence workflow script.
- `workflow/converge_multi.mjs` — the multi-PR fan-out driver: one `converge.mjs` child run per PR in parallel, each pinned to its PR worktree via `repoPath`.
- `workflow/aggregate_runs.py` — merges every autoconverge journal for a PR into one journal and returns its deduped findings, fix summaries, round count, and final SHA.
- `workflow/convergence_summary.py` — builds the convergence-summary agent prompt over a PR's merged findings.
- `workflow/render_report.py` — builds the closing convergence insights HTML report, taking the summary from `--summary-file`.
- `workflow/autoconverge_report_constants/` — named constants for the report builder and the summary prompt.
- `reference/` — convergence definition, stop conditions, gotchas, closing report.
