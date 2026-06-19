# workflow

Workflow scripts and report utilities for the `autoconverge` skill.

## Key files

| File | Role |
|---|---|
| `converge.mjs` | Main convergence workflow script. Each round runs Bugbot, code-review, and bug-audit lenses in parallel, deduplicates findings, applies fixes, pushes, gates on Copilot, checks convergence, and marks the PR ready. Runs via the `Workflow` tool — not directly with Node. |
| `aggregate_runs.py` | Merges every autoconverge journal for a given PR (matched by run id) into one merged journal. Prints a JSON line with `mergedJournal`, `roundCount`, `finalSha`, and `findingCount`. |
| `convergence_summary.py` | Builds the convergence-summary agent prompt over the merged journal's findings. The teardown step spawns a `general-purpose` subagent on this prompt. |
| `render_report.py` | Builds the closing HTML insights report. Takes `--journal`, `--summary-file`, `--out`, `--pr`, `--final-sha`, and `--rounds`. Writes the HTML to `--out` and prints the output path on stdout. |
| `autoconverge_report_constants/` | Named constants package for `render_report.py` and `convergence_summary.py`. |
| `converge.contract.test.mjs` | Contract tests for `converge.mjs` — verify the workflow interface and step ordering. |
| `converge.clean-audit.test.mjs` | Tests the clean-audit path (all lenses clean on first round). |
| `converge.copilot-gate.test.mjs` | Tests Copilot gate behavior (bypass on quota exhaustion). |
| `converge.fix-progress.test.mjs` | Tests fix-progress tracking across rounds. |
| `converge.fix-recovery.test.mjs` | Tests recovery when a fix commit fails. |
| `converge.run-input.test.mjs` | Tests workflow input validation. |
| `test_aggregate_runs.py` | Tests for `aggregate_runs.py`. |
| `test_convergence_summary.py` | Tests for `convergence_summary.py`. |
| `test_render_report.py` | Tests for `render_report.py`. |
| `fixtures/` | Test fixture data for the workflow tests. |
