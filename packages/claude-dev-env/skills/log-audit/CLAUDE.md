# log-audit

Reads this repository's own logs, finds recurring errors and timing regressions, and turns each real pattern into a tracked fix. Triggered by `/log-audit`, `audit the logs`, `what keeps failing`, or `what's getting slower`.

## Purpose

The skill runs as a background agent on a recurring schedule. Each cycle it reads the hook block log and the diagnostic extractor pipeline, clusters recurring errors and timing regressions, opens a grouped draft fix pull request or a tracked optimization issue per finding, and mines the defects Copilot and Bugbot keep catching into skill-edit proposals. Cycle state lives under `~/.claude/runtime/log-audit/`, so a restart resumes the same run.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Full instructions: the cycle steps, the three scripts and how to pipe them, the log sources in and out of scope, finding-filing rules, reviewer mining, cycle state, and cadence. |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | The agent charter — the fixed contract the skill answers to. |
| `scripts/` | The collect, cluster, and mine scripts and their constants package. |
