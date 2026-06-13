# Closing Report

When an autoconverge run converges (the workflow returns `converged: true`), the main session generates a convergence insights HTML report and publishes it as a secret gist with an idempotent PR comment linking to it.

## Data source

The report reads two file types written by the workflow during the run:

- **Run journal** — `~/.claude/projects/**/workflows/wf_<runId>.json` — the PR args, round log lines, `workflowProgress` array (one entry per agent step), and the final result.
- **Agent transcripts** — `~/.claude/projects/**/subagents/workflows/<runId>/agent-<agentId>.jsonl` — one file per agent; each line is a JSON object; the renderer extracts the last `StructuredOutput` tool_use from each file.

`converge.mjs` is not modified. The report is a pure reader of files the workflow already writes.

## Building the report

```
python "<skill>/workflow/render_report.py" \
  --journal "<journal path>" \
  --out "<output path>.html" \
  --pr <owner>/<repo>#<n> \
  --final-sha <sha> \
  --rounds <N> \
  --repo <worktree path>
```

The script reads the journal and transcripts, computes aggregated metrics (findings by severity, round, and theme; fix commits; tests added per round), and writes a self-contained HTML report. It prints the output path to stdout and exits 0 on success.

All aggregation is deterministic: `generated_date` comes from the journal `timestamp`, not the system clock, so the same inputs always produce the same HTML.

## Publishing

After rendering, the main session:

1. **Uploads the HTML as a secret gist** using `doc-gist/scripts/gist_upload.py --no-open`. Captures the htmlpreview URL from stdout.
2. **Posts one idempotent PR comment** marked with `<!-- autoconverge-report -->`. If a comment with that marker already exists on the PR, it is edited in place; otherwise a new comment is created. The comment body has the gist URL and a summary of findings by severity, rounds, and tests added, followed by the full finding list grouped by severity (`file:line — P# — title`). Write the body to a BOM-free temp file and pass `--body-file` to `gh issue comment` (never `--body`), or use the GitHub MCP `add_issue_comment` tool.
3. **Opens the report** with `Start-Process chrome -ArgumentList '--new-window', '<report path>'`. A missing Chrome does not abort teardown.

## Live-dashboard seam

The marker comment and gist together form a seam for future per-round dashboard refreshes: a live-dashboard step re-renders with the same `render_report_html` function (pure, no side effects), runs `gh gist edit` on the same gist, and edits the same marker comment. That per-round refresh path is out of scope here; this document describes the one-shot closing report only.

## Scope

The closing report runs only when `converged === true`. On a blocker exit (`blocker: "budget"` or similar), the report, gist, comment, and Chrome open are all skipped.
