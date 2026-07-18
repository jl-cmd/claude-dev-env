---
name: autoconverge
description: >-
  Drives one draft PR to convergence in one autonomous run with a host-selected
  pacer. On workflow: three parallel lenses (code-review, bug-audit, self-review)
  and one-commit fixes via converge.mjs. On portable: pr-converge continuous ticks
  via portable-driver.md. Bugbot, Copilot, and Codex as terminal confirmation
  gates before ready. Use when the user says '/autoconverge', 'autoconverge this
  PR', 'converge this PR in one run', 'run the converge workflow', or 'drive the
  PR to ready autonomously'.
---

# Autoconverge

One launch drives the whole loop to convergence. The `/autoconverge` skill
scans the tool list, selects a **pacer** (Workflow or portable), then resolves
PR scope, enters a worktree, grants project permissions, and drives the shared
converge product to ready (or a named blocker).

| Pacer | Host surface | How the loop runs |
|---|---|---|
| `workflow` | Tool list includes `Workflow` | `converge.mjs` background pass; state in the workflow journal |
| `portable` | `Workflow` absent | Continuous in-session ticks per [`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md); same helpers and `check_convergence.py` ready definition |

`pr-converge` selects `schedule_wakeup` or `portable` the same way. Both
entry skills share the helper scripts and the convergence gate.

## Run scope: one PR or several

Decide the scope from how many PRs the user named, then follow that path:

1. **One PR** → the single-PR run described below: one worktree, one pacer
   launch (`converge.mjs` on `pacer=workflow`, portable continuous ticks on
   `pacer=portable`), one teardown.
2. **Several PRs** → the [Multiple PRs](reference/multi-pr.md) run: on
   `pacer=workflow`, `workflow/converge_multi.mjs` drives every PR in parallel;
   on `pacer=portable`, run the portable driver once per PR (serial or host
   fan-out), then one teardown per PR.

The single-PR sections (Requirements, Pre-flight, Run the workflow or portable
driver, Teardown) each describe one converge run. The multi-PR reference reuses
them once per PR and adds only what fanning out needs: a per-PR worktree and a
per-PR teardown loop.

## Requirements

Scan the tool list for `Workflow` and `ScheduleWakeup`, then select the pacer:

```
python "$HOME/.claude/skills/_shared/pr-loop/scripts/select_converge_pacer.py" \
  --skill autoconverge \
  --has-workflow <0|1> \
  --has-schedule-wakeup <0|1>
```

- `pacer=workflow` — continue with Pre-flight and **Run the workflow** below.
- `pacer=portable` — continue with Pre-flight (portable worktree rules when
  `EnterWorktree` is absent), then the continuous driver in
  [`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md).
  **Do not abort** because the Workflow tool is missing.

Transport still needs authenticated GitHub access for the PR's owner (`gh` or
`pr-loop-cloud-transport`).

## Review-lens boundary

The code-review lens boundary (workflow agent versus the built-in `/code-review`
command) is defined on the **Code-review lens** bullet in
[`reference/convergence.md`](reference/convergence.md).

## Transport check (before any GitHub step)

Run `command -v gh`; when it succeeds, run `gh auth status`; once the PR
scope is resolved, run `gh api repos/<owner>/<repo> --jq .permissions.push`
and take `true` as the pass. When any check fails, run the
`pr-loop-cloud-transport` skill first and route every `gh` operation in this
skill through its substitution matrix. The workflow script
(`workflow/converge.mjs`) embeds `gh` commands and gh-backed helper scripts in
its agent prompts, so a cloud run also applies the same substitution to those
agent prompts when it authors the launch — the transport skill covers the
orchestrating session's own steps, and the script's agent-prompt text carries
`gh` calls the spawned agents cannot run in a cloud session.

## Pre-flight (main session)

0. **Build the task list (step 1 of every run).** After Copilot quota / down
   flags and Codex required/down are known, run only:

   ```
   python "$HOME/.claude/skills/_shared/pr-loop/scripts/build_converge_task_list.py" \
     --bugbot-down <0|1> --copilot-down <0|1> \
     --codex-down <0|1> --codex-required <0|1>
   ```

   Register every `tasks[]` entry on the session task list. **Final task** is
   always `all_runnable_reviews_clean_same_head` (`done_when` in the JSON).
   The run is complete only when that final task is completed — all runnable
   code reviews CLEAN on the same HEAD. Do not invent tasks in prose. On
   `pacer=portable`, `open-run` returns the same list; still register it as
   step 1 before driving reviews.

1. **Enter a worktree.** When `EnterWorktree` is in the tool list, call it with
   no arguments before any `gh`, `git`, file read, or edit. `gh`/`git` Bash
   calls do not auto-isolate, so isolation is mandatory. If it fails, report
   and stop. A bare `EnterWorktree` branches from `origin/main`; step 2
   positions the worktree on the PR's head ref. When `EnterWorktree` is
   absent, isolate with git worktree machinery per
   [`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md)
   § Isolation and worktree, then continue step 2.

2. **Resolve PR scope.** When the user passed a PR URL or number, parse owner,
   repo, and number from it. Otherwise read the current branch's PR:
   `gh pr view --json number,headRefName,url,isDraft,baseRefName`. Capture
   `owner`, `repo`, `prNumber`. Confirm the PR is a draft; if it is already
   ready, mark it draft first (`gh pr ready <n> --repo <o>/<r> --undo`) so the
   loop owns the ready transition.

   **Position the worktree on the PR branch.** The run reviews
   `git diff origin/main...HEAD` against this worktree's local `HEAD` and pushes
   each fix to the PR branch, so the worktree sits on the PR's head ref at the PR
   HEAD before the loop starts. A worktree fresh off `origin/main` has
   `HEAD == origin/main`, shows an empty diff, and reports a false convergence
   with zero findings. When a local worktree already tracks the PR branch, enter
   that one (pass its path to `EnterWorktree` when that tool exists; otherwise
   `cd` into it). Otherwise put the checkout on the branch with
   `gh pr checkout <number> --repo <owner>/<repo>`
   (or `git fetch origin <headRefName>` then `git switch <headRefName>`). Confirm
   before launching: `git rev-parse --abbrev-ref HEAD` equals the PR's head ref
   and local `HEAD` equals the PR head SHA.

3. **Verify the worktree is the PR's repo (strict pre-flight).** Run
   `python "$HOME/.claude/skills/_shared/pr-loop/scripts/preflight_worktree.py" --owner <owner> --repo <repo> --mode strict`.
   It confirms the working directory is a checkout of the PR's own repo and
   that `git worktree` machinery is healthy. A non-zero exit prints a
   `PREFLIGHT_OUTCOME` line and an `ABORT` line: report that line and stop.
   Autoconverge runs inside the PR's own repo, so a working directory rooted in
   a different repo (for example, `claude-dev-env` while the PR lives in
   `llm-settings`) or in no git checkout at all cannot continue.

4. **Grant project permissions.** Apply the `pr-loop-lifecycle` skill's Open
   section (`../pr-loop-lifecycle/SKILL.md`) — the grant command
   (`grant_project_claude_permissions.py`) and the auto-mode `AskUserQuestion`
   escalation for a blocked grant both live there.

5. **Copilot quota pre-check.** Before the pacer starts the loop, apply the
   `reviewer-gates` skill's Copilot quota gate (`../reviewer-gates/SKILL.md`)
   once. Exit 0 maps to `copilotDisabled: false` / `copilot_down=false`; any
   non-zero exit maps to `copilotDisabled: true` / `copilot_down=true`, and the
   run skips the Copilot gate with no agent spawned.

6. **Branch on pacer.** When `pacer=portable`, follow
   [`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md)
   § Continuous tick loop and § Autoconverge entry on portable pacer, then
   skip **Run the workflow** (no Workflow tool). When `pacer=workflow`,
   continue with **Run the workflow**.

## Run the workflow

(`pacer=workflow` only.) Call the `Workflow` tool against the colocated script:

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

The moment the `Workflow` call returns its run id, write the durable handoff so a
fresh session can resume the same run:

```
python "$HOME/.claude/skills/_shared/pr-loop/scripts/write_handoff.py" \
  --pr-number <N> --head-ref <branch> --phase workflow \
  --resume-command "Workflow({scriptPath, resumeFromRunId: '<runId>'})" \
  --run-id <runId>
```

Write it again when the result lands, so the handoff carries the final run id and
names the teardown phase the fresh session picks up from.

The workflow returns
`{ converged, rounds, finalSha, blocker, standardsNote, copilotNote, codexNote, cleanAuditNote, reuseNote, deferredPrs }`,
plus a `userReview` field on a `blocker: "user-review"` return. `cleanAuditNote` is
non-null when the environment refused the CLEAN bugteam review post and the run
recorded the bypass — see
[`reference/stop-conditions.md`](reference/stop-conditions.md) § Clean-audit post
bypassed.
`deferredPrs` is the list of draft environment-hardening PRs the standards-deferral
path opened this run, each as `{ owner, repo, prNumber, copilotDisabled, bugbotDisabled }`.
The two flags carry this run's Copilot and Bugbot availability, so the next generation
skips a reviewer that is down or out of quota without re-probing. This list is the seed the
[self-closing loop](reference/self-closing-loop.md) converges next.

## Copilot findings — tier, verify, then route

The Copilot gate tiers each finding: a **self-healing** finding (style, type
hints, imports, formatting, magic-value extraction, test-only or doc-vs-code
fixes — nothing that changes observable runtime behavior) flows into the fix
round with no user notification. A **code-concern** finding (logic, security,
data handling, error-handling semantics, concurrency — the tier whenever in
doubt) goes to a verification stage before any routing.

Each code-concern finding gets its own verifier agent, all in parallel, inside
the workflow. A verdict is conclusive only when an actual check ran: the verifier
executes a command against the flagged HEAD — running the code path with crafted
inputs, forcing the claimed error condition, or running a purpose-built test —
and captures its output. The verdict carries
`{ verdict, checkCommand, checkOutput, evidence }`; a conclusive verdict with an
empty `checkCommand` or `checkOutput` downgrades to inconclusive.

- **confirmed** — the check reproduces the defect. The finding becomes
  self-healing: it joins the fix round carrying its repro, and the fix re-runs
  that same check, adds a regression test where the suite covers the surface,
  lands in one commit, pushes, and replies on the thread with the fix SHA and the
  before/after output. No page.
- **refuted** — the check shows the code already behaves correctly in the exact
  scenario the finding claims is broken. The workflow replies on the thread with
  the command and output, resolves it, and counts it clean. No page.
- **inconclusive** — everything else, and the verifier's default: no runnable
  check exists, the check is infeasible here, the results are ambiguous, or the
  fix needs a product decision. Any doubt sorts here. Only inconclusive findings
  page the user.

A round whose code concerns all confirm or refute never returns
`blocker: "user-review"`. On one or more inconclusive findings, the workflow
stops with `converged: false`, `blocker: "user-review"`, and a `userReview`
field carrying
`{ reviewUrl, findings: [{ file, line, severity, tier, title, evidence }] }` —
`evidence` is the verifier's one-line note stating what check was attempted and
why it was not decisive.

The wait for a human belongs to the orchestrating session. On a
`blocker: "user-review"` return, run the
[`copilot-finding-triage`](../copilot-finding-triage/SKILL.md) skill for the ntfy
page only (the per-finding summary and evidence note plus the `reviewUrl`
Copilot review link), then hold for the user's response by pacer. On
`pacer=portable`, override triage's hold step — ntfy plus the portable hold
below; do not follow triage's `ScheduleWakeup` / `send_later` path.

- **`pacer=workflow`** — triage hold: 45-minute `ScheduleWakeup` (or
  `send_later` when that is the host arm).
- **`pacer=portable`** — portable hold only: in-session poll or handoff per
  [`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md);
  never `ScheduleWakeup` or `send_later`.

When the user answers within the window, follow their direction. When the
window closes with no response, run normal teardown and report the
inconclusive findings un-reviewed.

## Budget stop

Branch the stop and resume path on the selected pacer. Full rule:
[`reference/stop-conditions.md`](reference/stop-conditions.md) § Budget stop.

- **`pacer=workflow`** — `converge.mjs` paces against the workflow `budget` API
  and stops at a round boundary when a full round does not fit. On a
  `blocker: "budget"` return, write the durable handoff with the run id and the
  `Workflow({scriptPath, resumeFromRunId})` resume command before stopping, so a
  fresh session resumes the paced run without the stopped session's transcript.
- **`pacer=portable`** — stop at a tick boundary when the session cannot cover a
  full clean tick; write the durable handoff and resume with
  `/autoconverge <PR URL>` (see
  [`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md)).
  Do not instruct a Workflow resume on the portable path.

## Teardown

### `pacer=portable`

Skip Workflow-only report steps that need a workflow run id (journal merge,
HTML closing report, Artifact publish). Run `pr-loop-lifecycle` Close
(description rewrite when converged, working-tree clean, permission revoke)
and print the final report block using tick/`check_convergence` outcomes.
User-review holds use the portable in-session poll (or handoff) from
[`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md)
— not `ScheduleWakeup`. Resume command: `/autoconverge <PR URL>`.

### `pacer=workflow` (on workflow completion)

Teardown runs as an ordered checkpoint list. After each checkpoint finishes,
re-write the durable handoff with `--phase teardown`, the run id, and the
checkpoints done so far, so a fresh session that resumes reads `handoff.json`
`completed_steps` and skips the checkpoints already done:

```
python "$HOME/.claude/skills/_shared/pr-loop/scripts/write_handoff.py" \
  --pr-number <N> --head-ref <branch> --phase teardown \
  --resume-command "/autoconverge <PR URL>" \
  --run-id <runId> \
  --completed-steps "<checkpoints done so far>"
```

The checkpoints run in this order: `report`, `close`. Write the
handoff after each one finishes.

On teardown entry, when `~/.claude/runtime/pr-loop/bugteam-pr-<N>/handoff.json`
exists, read its `completed_steps` and skip any checkpoint the list already
names, so a resumed run performs only the checkpoints left.

On a `blocker: "user-review"` return under `pacer=workflow`, the workflow held
one or more code-concern findings that stayed inconclusive after the
executed-check verification stage. Run the
[`copilot-finding-triage`](../copilot-finding-triage/SKILL.md) gate before
teardown: send the ntfy alert with the per-finding summary and evidence note and
the `userReview.reviewUrl` link, then hold with a 45-minute `ScheduleWakeup` (or
`send_later` when that is the host arm). Act on the user's direction when it
arrives inside the window; when the window closes with no response, fall through
to normal teardown and report the `userReview.findings` un-reviewed. The PR
stays a draft in this path — the workflow marked nothing ready. Under
`pacer=portable`, use the portable teardown hold above (ntfy plus in-session
poll or handoff; never `ScheduleWakeup`).

Before the checkpoints, when the workflow returned a non-null `copilotNote`
(the Copilot gate was bypassed), query the PR's reviews once more for a
`copilot-pull-request-reviewer[bot]` review on the final HEAD
(`fetch_copilot_reviews.py`, or the GitHub MCP `pull_request_read` method
`get_reviews`). Copilot typically posts within 10–15 minutes of a request, so
a review can land between the bypass and teardown. When one exists and
carries findings, mark the PR draft, route the findings through one fix
round per the `pr-fix-protocol` skill, re-verify, push, and mark the PR
ready again — then run the checkpoints.

1. **When `converged` is true — build and publish the closing report.**
   Skip this entire step (report, artifact publish, comment, Chrome open) when
   the workflow returned a non-null `blocker`. Follow
   [`reference/closing-report.md`](reference/closing-report.md) § Building the
   report and § Publishing: resolve the seed journal from the run id, merge the
   PR's runs with `aggregate_runs.py`, spawn the `convergence-summary` agent
   (a `general-purpose` subagent) on the prompt it builds, draw the report with
   `render_report.py`, publish the HTML via the `Artifact` tool, post the
   one marker-keyed `<!-- autoconverge-report -->` PR comment, and open the
   artifact URL in Chrome. After the report is published, write the handoff
   with `--completed-steps "report"`.

2. **Close the run.** Apply the `pr-loop-lifecycle` skill's Close section
   (`../pr-loop-lifecycle/SKILL.md`): when `converged` is true, rewrite the PR
   description and clean the working tree — see
   [`pr-loop-lifecycle/reference/teardown-publish-permissions.md` § Clean working tree and § Publish the final PR description](../pr-loop-lifecycle/reference/teardown-publish-permissions.md);
   the workflow already marked the PR ready. The permission revoke always runs,
   including on a blocker exit. Write the handoff with
   `--completed-steps "report,close"`.

3. **Print the final report:**

   ```
   /autoconverge exit: <converged | blocked>
   Rounds: <N>
   Final commit: <finalSha>
   Blocker: <blocker>        # only when blocked
   Standards: <standardsNote> # only when a round deferred code-standard findings
   Copilot: <copilotNote>     # only when Copilot was down or out of quota
   Codex: <codexNote>         # only when the Codex gate was bypassed (codex_down or opt-out)
   Clean-audit: <cleanAuditNote> # only when the CLEAN bugteam post was bypassed
   Reuse: <reuseNote>         # only when the reuse pass identified an improvement
   ```

## What the workflow does each round

[`reference/convergence.md`](reference/convergence.md) defines the whole loop:
the merge-conflict pre-flight, the reuse pass and its three landing criteria,
the round shape (static sweep, the three parallel reading lenses, dedup, the
one-commit fix flow, the standards-deferral path), the terminal Bugbot, Copilot,
and Codex gates, the per-role model tiers, the full-diff rule, and the exact
ready definition `check_convergence.py` enforces.
[`reference/stop-conditions.md`](reference/stop-conditions.md) lists every way
the run ends short of ready. Hard-won failure lessons live in
[`reference/gotchas.md`](reference/gotchas.md).

Every agent prompt the workflow authors carries a headless-safety preamble —
read-only agents get a trimmed form, edit agents the full form with the rm
auto-allow paths — specified in
[`reference/headless-safety.md`](reference/headless-safety.md).

## Multiple PRs

When the user names several PRs, run the multi-PR path in
[`reference/multi-pr.md`](reference/multi-pr.md): one worktree per PR
(`git worktree add` on each head ref, strict pre-flight per worktree, one
permission grant per repository, one Copilot quota check for the whole run),
then launch by pacer — `pacer=workflow`: one `workflow/converge_multi.mjs`
call with one entry per PR; `pacer=portable`: portable driver once per PR
(serial or host fan-out) — then single-PR teardown once per PR and a
one-line-per-PR summary.

## Self-closing loop: converge the deferred PRs

Every autoconverge run — single-PR and multi-PR alike — ends with the
self-closing loop in
[`reference/self-closing-loop.md`](reference/self-closing-loop.md): the
orchestrating session converges the draft environment-hardening PRs the run
deferred (`deferredPrs` on a single-PR run, `allDeferredPrs` on a multi-PR
run), then the PRs those runs defer, generation by generation, until a
generation opens none. An empty seed list ends the loop at once. The reference
also carries the Conventional-Commit title rule each hardening PR must meet.

## Folder map

- `SKILL.md` — this hub.
- [`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md) — portable pacer when `Workflow` is absent.
- `workflow/converge.mjs` — the convergence workflow script.
- `workflow/converge_multi.mjs` — the multi-PR fan-out driver: one `converge.mjs` child run per PR in parallel, each pinned to its PR worktree via `repoPath`.
- `workflow/aggregate_runs.py` — merges every autoconverge journal for a PR into one journal and returns its deduped findings, fix summaries, round count, and final SHA.
- `workflow/convergence_summary.py` — builds the convergence-summary agent prompt over a PR's merged findings.
- `workflow/render_report.py` — builds the closing convergence insights HTML report, taking the summary from `--summary-file`.
- `workflow/autoconverge_report_constants/` — named constants for the report builder and the summary prompt.
- `reference/convergence.md` — the whole loop: reuse pass, round shape, terminal gates, model tiers, ready definition.
- `reference/stop-conditions.md` — every way the run ends short of ready, including the budget stop.
- `reference/gotchas.md` — hard-won failure lessons.
- `reference/closing-report.md` — the closing HTML report: data source, build steps, publishing.
- `reference/multi-pr.md` — the several-PRs path: per-PR worktrees, the `converge_multi.mjs` launch, per-PR teardown.
- `reference/self-closing-loop.md` — the deferred-PR generations and the Conventional-Commit title rule.
- `reference/headless-safety.md` — the agent-prompt preamble and the rm auto-allow paths.
