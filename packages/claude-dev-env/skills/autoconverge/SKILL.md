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
`{ converged, rounds, finalSha, blocker, standardsNote, copilotNote }`.

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
        --rounds <roundCount> \
        --repo <worktree>
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
   ```

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
suite (`python -m pytest`) and keep scratch work in ephemeral temp dirs.

- **Converge:** `parallel([Bugbot lens, code-review lens, bug-audit lens])` on
  the current HEAD, full `origin/main...HEAD` diff. Dedup findings; one
  `clean-coder` applies all fixes in a single commit, pushes, replies to and
  resolves any bot threads; re-verify next round on the new HEAD. When all
  three are clean on a stable HEAD, post the CLEAN bugteam audit artifact.
  A round whose findings are ALL code-standard violations (pure CODE_RULES/style,
  no behavioral impact) passes for convergence purposes: the workflow files a
  follow-up issue listing the findings, opens a draft environment-hardening PR
  (hooks/rules that block those violation classes at Write/Edit time), resolves
  any bot threads with a deferral note, and reports the deferral in
  `standardsNote`.
- **Copilot gate:** request a Copilot review, poll up to three times; findings
  route back into Converge. When Copilot is down or out of quota — it posts an
  out-of-usage notice (the requester hit their quota) on the HEAD, or surfaces no
  review at all after the cap — the gate logs a notice and the run marks the PR
  ready with the Copilot gate bypassed. `copilotNote` records the bypass.
- **Convergence check:** `check_convergence.py` is the authoritative gate; on a
  full pass the workflow marks `draft=false`.

## Folder map

- `SKILL.md` — this hub.
- `workflow/converge.mjs` — the convergence workflow script.
- `workflow/aggregate_runs.py` — merges every autoconverge journal for a PR into one journal and returns its deduped findings, fix summaries, round count, and final SHA.
- `workflow/convergence_summary.py` — builds the convergence-summary agent prompt over a PR's merged findings.
- `workflow/render_report.py` — builds the closing convergence insights HTML report, taking the summary from `--summary-file`.
- `workflow/autoconverge_report_constants/` — named constants for the report builder and the summary prompt.
- `reference/` — convergence definition, stop conditions, gotchas, closing report.
