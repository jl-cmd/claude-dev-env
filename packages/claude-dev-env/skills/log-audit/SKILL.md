---
name: log-audit
description: >-
  Watches this repo's own logs for patterns worth acting on. Use for /log-audit,
  "audit the logs", "what keeps failing", or "what's getting slower". Reads the
  hook block log and the diagnostic extractor pipeline, clusters recurring errors
  and timing regressions, opens a grouped fix PR or a tracked optimization issue
  per real finding, and mines the defects Copilot and Bugbot keep catching into
  skill-edit proposals. Runs as a background agent that resumes after a restart.
---

# log-audit

Read the logs this repo writes about itself, find what keeps going wrong or keeps getting slower, and turn each real pattern into a tracked fix. `reference/charter.md` holds the full contract; this file is how to run a cycle.

## One cycle

1. **Collect.** Run `scripts/collect_log_window.py` to read the recent window of the hook block log into records.
2. **Cluster.** Pipe those records into `scripts/cluster_recurrences.py` to group them by a normalized signature and rank the loudest first. When timing samples are on hand, the same module flags operations whose recent runs have grown slower than their earlier runs.
3. **Mine reviewers.** Run `scripts/mine_copilot_findings.py` to sort recent reviewer-bot comments into defect classes and print a skill-edit proposal for each class.
4. **File findings.** For each real finding, open a grouped fix pull request as a draft, or file a tracked optimization issue for a delay.
5. **Report.** Write the per-cycle report: delays removed, pull requests opened, skill improvements suggested.
6. **Re-arm.** Save cycle state and schedule the next cycle.

## Scripts

| File | What it does |
|---|---|
| `scripts/collect_log_window.py` | Tails the JSON-lines hook block log and prints the block records inside a time window as JSON. `--hours` sets the window; `--log-path` overrides the log location. |
| `scripts/cluster_recurrences.py` | Reads that JSON on stdin, groups records by a normalized message signature, and prints the clusters ranked by recency-weighted count. Its `detect_timing_regressions` flags an operation whose recent runs are slower than its earliest runs. |
| `scripts/mine_copilot_findings.py` | Reads a repo's reviewer-bot comments through `gh`, sorts them into defect classes, and prints one skill-edit proposal per class, most frequent first. Takes `--repo owner/name`. |

Run the first two as a pipeline:

```
python scripts/collect_log_window.py --hours 24 | python scripts/cluster_recurrences.py
```

## What it reads

In scope:

- The hook block log at `~/.claude/logs/hook-blocks.log`, written by `hook_block_logger`.
- The `hooks/diagnostic/` extractor pipeline. When Neon is set up, read through that pipeline's SQL — the shape of `queries/blocks_by_category.sql` and its siblings against the `hook_events` table, which carries `duration_ms` for timing work. When Neon is not set up, read the flat `hook-blocks.log` directly. Reuse the diagnostic pipeline's helpers; do not hold a second copy.

Out of scope: Samsung-automation logs. Read this repo's log surfaces only.

## Filing findings

- A pull request or optimization issue carries its body in a file passed by path, following the `gh-body-file` rule.
- Any paginated GitHub read follows the `gh-paginate` rule.
- Group the related fixes for one finding into a single draft pull request rather than one PR per line.

## Reviewer-defect mining

`mine_copilot_findings.py` names a skill or rule edit for each defect class the reviewers keep catching — an edit that would block that class at write time rather than at review. These are proposals. A human applies them through review; the agent does not commit them on its own.

## Cycle state and restart survival

The agent keeps its state in a JSON file under `~/.claude/runtime/log-audit/` — the last window it read, the signatures it already reported, and the open items it filed. At the start of each cycle, read that file; at the end, write it back. Because the state lives in the durable runtime directory rather than the OS temp directory, a restart reads the same file and resumes the same run.

## Cadence

The agent runs on a recurring schedule following the repository's Scheduled Task Cadence: a sub-hour interval, with a 30-minute default. Re-arm the next cycle with `ScheduleWakeup` for a self-paced loop, or register a cron routine through `/schedule` for a fixed clock cadence.

## Per-cycle report

Each cycle ends with a short report: the delays removed, the pull requests opened, and the skill improvements suggested.
