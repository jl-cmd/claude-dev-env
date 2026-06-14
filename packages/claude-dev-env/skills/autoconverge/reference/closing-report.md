# Closing Report

When an autoconverge run converges (the workflow returns `converged: true`), the main session generates a convergence insights HTML report and publishes it as a secret gist with an idempotent PR comment linking to it.

## Data source

A PR's full convergence is the union of every autoconverge run it took. `aggregate_runs.py` finds all of them and merges them into one run tree the report reads:

- **Run journals** — `~/.claude/projects/**/workflows/wf_<runId>.json` — each carries the PR args, round log lines, a `workflowProgress` array (one entry per agent step), and the run result. `aggregate_runs.py` picks every journal whose `args` owner/repo/prNumber match the PR and whose `workflowName` is `autoconverge`, orders them by timestamp, and concatenates their `workflowProgress` into one merged journal under the work directory.
- **Agent transcripts** — `~/.claude/projects/**/subagents/workflows/<runId>/agent-<agentId>.jsonl` — one file per agent; each line is a JSON object. The merge copies every referenced transcript into the merged run tree, so the report reader extracts the last `StructuredOutput` tool_use from each exactly as it would for a single run.

The merged journal's round count is the number of `resolve-head` steps across every run, and its final SHA is the latest run's result SHA.

## Convergence summary

The plain-language account of what the PR does and what the run caught is written at teardown, over the merged findings. `convergence_summary.py` builds the agent prompt from the deduped findings and the per-round fix summaries `aggregate_runs.py` returns; the teardown spawns a `convergence-summary` agent on that prompt; the agent's JSON answer is the summary. `render_report.py --summary-file <path>` reads that JSON and draws from it, so the summary needs no journal transcript of its own.

The summary carries the structured visual data the report draws:

- `prProblem` and `prFix` — one plain sentence each: the problem this PR solves and the change that solves it.
- `problemScenes` and `fixScenes` — short cause→effect scenes. Each scene has a `trigger`, an optional `condition`, a `result`, and a one-line `caption`. A fix scene mirrors a problem scene with a good result.
- `verdictLine` — one factual sentence: converged, the distinct issue-class count, all fixed or deferred.
- `issueClasses` — one entry per distinct kind of problem, each with a `plainName`, a `count`, a `severity`, a `category`, a `status`, a plain `cause`, a `medium` (`terminal`, `code`, or `text`) that tells the report how to draw the before/after panels, and the literal `beforeLines` and `afterLines` shown in those panels. There is one class per kind, however many kinds there are — kinds are never folded together or dropped to hit a number.

Python owns the counts, severity, and file:line; the summary agent owns the plain-language narrative. The report draws the same HTML each time it runs over the same merged journal and summary.

## What the report draws

The report body, in order:

1. A title and a subtitle (owner/repo, component when it can be derived, finding count over round count, date).
2. A **verdict banner** — a check circle, the `verdictLine`, and a Python-computed line giving the fix-commit count and the final short SHA.
3. **What this PR does** — a problem card and a fix card. Each card draws its scenes as a trigger chip → optional condition → result, each with its caption. When a scene list is empty, the card falls back to drawing `prProblem` or `prFix` as a single caption line.
4. **What was caught — and how it looked** — a lead line stating the bug-class count, the total finding count, the round count, and the fix-commit count, then one block per issue class: a name heading with a finding-count chip, a before panel and an after panel drawn in the style its `medium` names (a dark terminal window, a light code panel, or plain lines), and a cause line that states the plain cause plus a muted note with severity, category, count, and status. When both line lists are empty, the block drops to its heading and cause line.
5. A footer (owner/repo, PR, findings, rounds, fix commits, generated date).

A collapsed `<details>` raw-findings appendix (`file:line — P# — title`) closes the body and keeps the engineer grounding one click away.

When the summary is absent, the report falls back to a minimal layout: the title, the subtitle, a plain run-stats note, and the collapsed raw-findings appendix.

## Building the report

Three steps run at teardown, each a separate process:

1. **Merge the runs and build the summary prompt.**
   ```
   python "<skill>/workflow/aggregate_runs.py" \
     --journal "<seed journal path>" \
     --pr <owner>/<repo>#<n> \
     --work-dir "<work dir>" \
     --out-prompt "<prompt path>.txt" \
     [--standards-note "<note>"] [--copilot-note "<note>"]
   ```
   `--journal` is any one of the PR's journals — the seed that locates the rest. The script prints a JSON line carrying `combinedJournal`, `roundCount`, `finalSha`, and `findingCount`.

2. **Write the summary.** Spawn a `convergence-summary` agent on the prompt file's text. Its JSON answer — the `prProblem`/`prFix`/`problemScenes`/`fixScenes`/`verdictLine`/`issueClasses` object — goes to a `.json` file.

3. **Draw the report.**
   ```
   python "<skill>/workflow/render_report.py" \
     --journal "<combinedJournal>" \
     --summary-file "<summary json path>" \
     --out "<output path>.html" \
     --pr <owner>/<repo>#<n> \
     --final-sha <finalSha> \
     --rounds <roundCount> \
     --repo <worktree path>
   ```
   The script reads the merged journal and transcripts, counts findings by severity and fix commits, takes the summary from `--summary-file`, draws the visual report, and writes a self-contained HTML file. It prints the output path to stdout and exits 0 on success.

Counting is deterministic: `generated_date` comes from the journal `timestamp`, not the system clock, so the same merged journal and summary always produce the same HTML.

## Publishing

After rendering, the main session:

1. **Uploads the HTML as a secret gist** using `doc-gist/scripts/gist_upload.py --no-open`. Captures the htmlpreview URL from stdout.
2. **Posts one idempotent PR comment** marked with `<!-- autoconverge-report -->`. If a comment with that marker already exists on the PR, it is edited in place; otherwise a new comment is created. The body leads with the gist URL, then the one-sentence `verdictLine`, then the plain Problem and Fix sentences (`prProblem`, `prFix`), then the issue-class list — one bullet per class as `plainName (×count, status)` — and closes with the full finding list (`file:line — P# — title`) inside a collapsed `<details>` block. Write the body to a BOM-free temp file and pass `--body-file` to `gh issue comment` (never `--body`), or use the GitHub MCP `add_issue_comment` tool.
3. **Opens the report** with `Start-Process chrome -ArgumentList '--new-window', '<report path>'`. A missing Chrome does not abort teardown.

## Live-dashboard seam

The marker comment and gist together form a seam for future per-round dashboard refreshes: a live-dashboard step re-renders with the same `render_report_html` function (pure, no side effects), runs `gh gist edit` on the same gist, and edits the same marker comment. That per-round refresh path is out of scope here; this document describes the one-shot closing report only.

## Scope

The closing report runs only when `converged === true`. On a blocker exit (`blocker: "budget"` or similar), the report, gist, comment, and Chrome open are all skipped.
