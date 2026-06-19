# pr-converge skill

Drives a draft PR to convergence by looping Cursor Bugbot, a code-review pass, a second-opinion bug audit (`bugteam`), and Copilot — applying TDD fixes, posting inline replies, and re-triggering reviewers each tick until all reviewers are clean on the same HEAD and the PR is mergeable.

**Trigger:** `/pr-converge`, "drive PR to convergence", "loop bugbot and bugteam", "babysit bugbot and bugteam", "until both are clean", "converge this PR".

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Full tick workflow, pre-flight checks, state schema, budget-aware tick boundaries, stop conditions |
| `pr_converge_skill_constants/constants.py` | Runtime and API constants (bot logins, review states, GH API path templates, regex patterns) |

## Subdirectories

| Directory | Role |
|---|---|
| `pr_converge_skill_constants/` | Importable constants module shared by skill scripts |
| `reference/` | Per-tick steps, convergence gates, fix protocol, obstacle runbooks, state schema, stop conditions, examples |
| `scripts/` | Python helpers (bugbot check, convergence check, Copilot review fetcher, fix-reply poster, reflow tool) and their tests |
| `workflows/` | ScheduleWakeup loop pacing specification |

## Conventions

- Each invocation runs one tick. The next tick is scheduled via `ScheduleWakeup` unless convergence or a stop condition has been reached.
- Loop state persists to `$CLAUDE_JOB_DIR/pr-converge-state.json` between ticks.
- The pre-flight gate requires `EnterWorktree` before any file read or API call, and confirms `ScheduleWakeup` is in the tool list.
- All findings and PR reports state verified facts only — no hedging language.
- The GitHub MCP (`pull_request_read`, `pull_request_review_write`) is the primary path for PR inspection; `gh api` is the fallback.
