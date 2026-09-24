# Report task usage

## What this does

The reporter records token use, available cost, and your pass or fail result for each task attempt. It reads vendor output from standard input and prints one JSON line. It runs only when you invoke it.

## Before you start

- Use Python 3.11 or newer. Run `python --version` to check.
- Keep the source output for one attempt in a private file. It may contain prompts, answers, and identifiers.
- Keep each input capture to one task attempt. The script rejects Claude telemetry from multiple sessions and Codex output with more than one thread start.
- Decide how you will judge the task before reading its answer. The reporter cannot judge the answer for you.
- Open PowerShell in the repository folder that contains `README.md`.

## Record one attempt

1. Set the script path in PowerShell.

   ```powershell
   $usageScript = 'packages/claude-dev-env/scripts/task_usage_report.py'
   ```

2. Judge the answer using your task check. Choose `pass` if it met the check, or `fail` if it did not.

3. Read one Claude headless JSON result and append its report to `task-usage.jsonl`.

   ```powershell
   Get-Content -Raw -LiteralPath '.\claude-output.json' |
       python $usageScript run --task-id task-7 --run-id run-1 --repository team/project --outcome pass --source-format claude-json |
       Add-Content -LiteralPath '.\task-usage.jsonl'
   ```

   Replace the file name, IDs, repository, and outcome with your values. Use the same task ID for retries and a new run ID for each attempt. A JSONL file holds one JSON object per line.

4. Check the saved line.

   ```powershell
   Get-Content -LiteralPath '.\task-usage.jsonl' | Select-Object -Last 1
   ```

   You should see your task ID, run ID, repository, outcome, token counts, `cost_usd`, and `cost_basis`. A missing source count or cost appears as `null`.

## Choose the source format

Use the same `run` command with the matching file and `--source-format` value.

| Source output | Format value | Capture rule | Cost basis |
| --- | --- | --- | --- |
| Claude headless JSON | `claude-json` | One `result` object | The result's reported total cost, or its per-model costs when no total is present |
| Claude OpenTelemetry JSON or JSONL | `claude-otel` | `claude_code.api_request` events from one `session.id` | Estimated `cost_usd` or `cost_usd_micros` event values |
| Codex JSON or JSONL | `codex-json` | One `thread.started` event and its `turn.completed` events | Token counts multiplied by the rates you supply |

For Codex cost, add `--rate 'MODEL=INPUT,WRITE,READ,OUTPUT'` for each model in the input. Enter four current USD prices per million tokens, in that order. Add `--rate-source SOURCE` with a short price-source label and `--rate-effective-date YYYY-MM-DD` with the date those prices apply. Add `--model MODEL` when the Codex events omit the model name. Without a required rate or token count, `cost_usd` is `null`.

For a capture with one Codex model, enter its prices and record the run in PowerShell.

```powershell
$rateSpec = Read-Host 'Enter MODEL=INPUT,WRITE,READ,OUTPUT'
$rateSource = Read-Host 'Enter a source label using letters, digits, dots, dashes, underscores, or slashes'
$rateDate = Read-Host 'Enter the price date as YYYY-MM-DD'
Get-Content -Raw -LiteralPath '.\codex-output.jsonl' |
    python $usageScript run --task-id task-7 --run-id run-2 --repository team/project --outcome pass --source-format codex-json --rate $rateSpec --rate-source $rateSource --rate-effective-date $rateDate |
    Add-Content -LiteralPath '.\task-usage.jsonl'
```

Replace the file name, IDs, repository, and outcome with this run's values. Use the same task ID only when this Codex run retries that task.

The report sets `cost_basis` to `provider_estimate` for Claude cost, `caller_rates` for Codex cost, or `unknown` when cost is missing. Compare runs using the same price basis and date. The reporter does not check an invoice.

To capture Claude OpenTelemetry events, set the exporter variables for the Claude process as shown in [Claude Code monitoring](https://code.claude.com/docs/en/monitoring-usage). Enable telemetry and a logs exporter, then provide its `api_request` JSON or JSONL to this script. This repository does not configure an OpenTelemetry collector. Raw API body logging is unnecessary for usage reporting.

For Codex, cached input and reasoning output are subsets of the input and output totals. The rate calculation charges each token once. The reporter combines repeated Claude request IDs or Codex turn IDs once. A conflicting duplicate stops the run with an error.

## Summarize tasks

1. Read the saved report lines with `summary`.

   ```powershell
   Get-Content -Raw -LiteralPath '.\task-usage.jsonl' |
       python $usageScript summary
   ```

2. Check `cost_per_passed_task_usd` in the printed JSON. The summary groups attempts by repository and task ID. It counts a task as passed if any attempt passed and includes the cost of every attempt, including tasks that never passed.

If any attempt lacks cost or outcome, or no task passed, the summary reports `status` as `unknown` and leaves cost per passed task as `null`. Check the missing report fields before comparing two pipelines.

## Privacy and limits

The reporter writes selected IDs, outcome, model names, counts, and cost. It does not copy prompts, answers, request bodies, or session IDs into the report. Choose IDs that contain no personal or secret text. A source file you saved still contains its original content; keep it private and remove it when you no longer need it.

The counts describe a whole attempt. The reporter cannot assign tokens to a system prompt, tool schema, file read, or message. Compare cost per passed task only after you have scored the tasks with the same checks.
