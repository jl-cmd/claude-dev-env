# claude-review

Thorough built-in Claude Code review on the full `origin/main...HEAD` diff:
`/code-review xhigh --fix` pinned to opus, with a session usage probe and
host-aware invoke via `invoke_code_review.py` (in-session on Claude+opus when
usage remains, chain on every other host/model and when the primary session is
drained). Triggered by `/claude-review`, `claude-review`, `code-review xhigh
--fix`, thorough review on opus, chain runner review, or colloquial
ultra-review.

## Purpose

One capability: run the thorough local built-in review path and interpret the
invoker outcome (`mode`, `served_command`, `returncode`, `dirty_tree`). Layer A
is the session usage probe; Layer B is headless serve through
`claude_chain_runner`. Static sweep and fix protocol stay in shared scripts /
`pr-fix-protocol`. Converge loops own phase stamps (`code_review_clean_at`) and
re-entry.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | When, refusals, sub-skills, process, probe + invoker CLI, gotchas |
| `reference/full-diff-and-clean-stamp.md` | Full-diff rule and clean-stamp contract |
| `reference/process-tasks.md` | Task seeds for a full review pass |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Progressive-disclosure pages for contracts and task seeds |

## Invoker surface

No skill-local scripts. Runtime lives in package `scripts/` (installed under
`$HOME/.claude/scripts/`):

| Path | Role |
|---|---|
| `../../scripts/claude_usage_probe.py` | Layer A: wraps usage-pause `resolve_usage_window` into skill-facing JSON |
| `../../scripts/invoke_code_review.py` | Host-aware entrypoint; forces chain when `--session-has-usage-left false` |
| `../../scripts/claude_chain_runner.py` | Layer B: headless chain; fail over only on usage-limit signatures |
| `../../scripts/dev_env_scripts_constants/code_review_constants.py` | Prompt, model pin, mode keys, session-has-usage-left CLI tokens |
| `../../scripts/dev_env_scripts_constants/claude_usage_probe_constants.py` | Session no-usage threshold and probe report keys |
