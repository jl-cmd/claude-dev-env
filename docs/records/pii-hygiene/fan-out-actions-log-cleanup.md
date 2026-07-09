# Fan-out workflow run cleanup (issue #948)

## Inventory

- Workflow: `.github/workflows/fan-out-ai-rules.yml` (workflow_id `262293813`)
- Retained runs for that workflow: **44**
- Confirmed leak surface: job logs print excluded and failed target repo full names (`owner/repo`) under `##[notice]` / `##[error]`
- Other CI jobs on this repo do not enumerate the private fleet the same way

## API notes

- `DELETE /repos/{owner}/{repo}/actions/runs/{run_id}` deletes one workflow run and its logs
- CLI: `gh run delete <run-id> --repo jl-cmd/claude-code-config`
- No bulk "purge all logs for workflow" endpoint; deletion is per `run_id`
- Deletion is irreversible

## Safe procedure (list first; delete only after human review)

```powershell
# 1) List and count — stop if the count is unexpected
$all_run_ids = gh api `
  "repos/jl-cmd/claude-code-config/actions/workflows/fan-out-ai-rules.yml/runs?per_page=100" `
  --jq ".workflow_runs[].id"
$all_run_ids.Count

# 2) Write IDs for review
$all_run_ids | Set-Content fanout-run-ids.txt

# 3) After human review of fanout-run-ids.txt, delete one-by-one:
# foreach ($each_run_id in Get-Content fanout-run-ids.txt) {
#   gh run delete $each_run_id --repo jl-cmd/claude-code-config
# }
```

## Status

- Code fix: Metric/Count summaries and redacted notices (PR for #948)
- Retained pre-fix logs: **not deleted** here; inventory above is ready for owner-approved deletion after the fix merges
