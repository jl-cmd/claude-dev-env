---
name: e-code-review
description: >-
  High-effort code review that matches the built-in /code-review high recipe:
  8 inline finder angles, dedup with no verify, at most 10 findings. Triggers:
  /e-code-review, /e-code-review high.
---

# e-code-review

**One level: `high`.** Load [reference/high.md](reference/high.md) and run it. The file is the built-in `/code-review high` recipe, word for word.

## Target

A PR number, branch name, or file path after the level is the review target. With no target, the review reads the current diff.

## The process

1. Load `reference/high.md`.
2. Run it end to end, ending in its ReportFindings call.
