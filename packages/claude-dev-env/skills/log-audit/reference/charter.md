# Log-Audit Agent Charter

The contract for the log-audit agent: what it watches, what it looks for, and what it produces each cycle. The skill body (`SKILL.md`) and its scripts carry out this contract; this document is the fixed reference they answer to.

## What the agent is

A background agent that reads this repository's own log surfaces, finds patterns worth acting on, and turns each real pattern into a tracked fix. It runs on its own without a person driving it and picks up where it left off after a restart.

## Cycle state and cadence

The agent keeps its own state on disk under `~/.claude/runtime/log-audit/`. This directory holds durable cycle state — the last window it read, the signatures it already reported, and the open items it filed — so a restart resumes the same run rather than starting over. The OS temp directory is not a home for this state, because temp files can be cleared between sessions.

The agent runs on a recurring schedule. It follows the repository's Scheduled Task Cadence: a sub-hour interval, with a 30-minute default.

## Log sources it reads

In scope:

- The hook block log at `~/.claude/logs/hook-blocks.log`, written by `hook_block_logger`. Each line is one JSON record naming the hook that blocked, the event, the reason, the tool, and a short input excerpt.
- The `hooks/diagnostic/` extractor pipeline. When Neon is configured, the agent reads through the pipeline's SQL — the shape of `queries/blocks_by_category.sql` and its siblings against the `hook_events` table, which carries `duration_ms` for timing work. When Neon is not configured, the agent reads the flat `hook-blocks.log` directly. It reuses the diagnostic pipeline's helpers rather than holding a second copy of them.

Out of scope:

- Samsung-automation logs. The agent reads this repository's log surfaces only.

## What it looks for

Two kinds of pattern:

- Recurring errors. The same failure showing up again and again. The agent groups log records by a normalized message signature — the message with its digits, paths, and hashes stripped — so records that differ only in those details fall into one cluster. It ranks clusters by count weighted toward recent activity.
- Timing regressions. The same operation taking longer over time. When a repeated operation's duration climbs across cycles, the agent flags it as an unnecessary delay, separate from any error.

## What it does per finding

For each real finding, the agent takes one of two tracked actions:

- Opens a grouped fix pull request as a draft, gathering the related fixes into one branch.
- Files a tracked optimization issue when the finding is a delay to chase rather than a fix to write.

Both paths carry their body in a file passed by path, following the `gh-body-file` rule, and any paginated GitHub read follows the `gh-paginate` rule.

## Reviewer-defect mining

The agent also reads the defect patterns that Copilot and Bugbot catch again and again across recent pull requests. It clusters those comments into defect classes and proposes concrete edits to the skill definitions that would block each class upstream, at the point of writing, rather than at review. These are proposals: they land through review, not by the agent applying them on its own.

## Per-cycle report

Each cycle ends with a short report covering:

- Delays removed.
- Pull requests opened.
- Skill improvements suggested.
