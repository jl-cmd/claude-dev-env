# claude-review

Thorough built-in Claude Code review on the full `origin/main...HEAD` diff:
`/code-review xhigh --fix` pinned to opus, host-aware via `invoke_code_review.py`
(in-session on Claude+opus, chain on every other host/model). Triggered by
`/claude-review`, `claude-review`, `code-review xhigh --fix`, thorough review on
opus, chain runner review, or colloquial ultra-review.

## Purpose

One capability: run the thorough local built-in review path and interpret the
invoker outcome (`mode`, `served_command`, `returncode`, `dirty_tree`). Static
sweep and fix protocol stay in shared scripts / `pr-fix-protocol`. Converge
loops own phase stamps (`code_review_clean_at`) and re-entry.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | When, refusals, sub-skills, process, invoker CLI, gotchas |
| `reference/full-diff-and-clean-stamp.md` | Full-diff rule and clean-stamp contract |
| `reference/process-tasks.md` | Task seeds for a full review pass |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Progressive-disclosure pages for contracts and task seeds |

## Invoker surface

Package scripts (installed under `$HOME/.claude/scripts/`):

| Path | Role |
|---|---|
| `invoke_code_review.py` | Host-aware entrypoint; JSON outcome on stdout |
| `dev_env_scripts_constants/code_review_constants.py` | Prompt (`xhigh`), model alias, result keys |
| `claude_chain_runner.py` | Binary failover chain for headless `-p` runs |
