---
name: e-code-review
description: >-
  Code review at one of five effort levels that match the built-in
  /code-review recipes word for word: low, medium, high, xhigh, max.
  Triggers: /e-code-review, /e-code-review low, /e-code-review medium,
  /e-code-review high, /e-code-review xhigh, /e-code-review max, and any
  level with --fix.
---

# e-code-review

**Pick a level, load its file, run it.** Each file is the built-in `/code-review` recipe for that level, word for word.

| Level | File | Shape |
|---|---|---|
| `low` | [reference/low.md](reference/low.md) | 1 diff pass, no verify, at most 4 findings |
| `medium` | [reference/medium.md](reference/medium.md) | 1 careful diff pass, at most 15 findings |
| `high` | [reference/high.md](reference/high.md) | 8 inline angles, dedup with no verify, at most 10 findings |
| `xhigh` | [reference/xhigh.md](reference/xhigh.md) | 10 inline angles, dedup, gap sweep, at most 15 findings |
| `max` | [reference/max.md](reference/max.md) | 10 subagent angles, 1-vote verify, gap sweep, at most 15 findings |

## Level

With no level, or an unknown one, run `high`.

## Target

A PR number, branch name, or file path after the level is the review target. With no target, the review reads the current diff.

## --fix

`--fix` works with every level. It lives in one file, [reference/fix.md](reference/fix.md). No level file carries its own fix steps.

## The process

1. Read the level and the optional `--fix` flag. Load the level file.
2. Run it end to end, ending in its ReportFindings call.
3. With `--fix`, load `reference/fix.md` and run it on those findings.
