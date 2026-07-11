# pr-converge/scripts

Python helper scripts for the `pr-converge` skill, plus their tests and a PowerShell/AutoHotkey toolset for advancing Cursor agents.

## Key files

| File | Purpose |
|---|---|
| `check_bugbot_ci.py` | Checks bugbot CI check-run status on a given SHA |
| `check_convergence.py` | Evaluates whether all convergence gates pass on the current HEAD |
| `check_pending_reviews.py` | Fetches pending review requests and reviewer states |
| `fetch_copilot_reviews.py` | Fetches Copilot reviewer reviews filtered to the current HEAD |
| `post_fix_reply.py` | Posts an inline reply to a review comment thread |
| `reflow_skill_md.py` | Reformats `SKILL.md` to enforce a line width limit |
| `README.md` | MCP tool reference for PR operations used by the scripts |
| `test_check_bugbot_ci.py` | Tests for `check_bugbot_ci.py` |
| `test_check_convergence.py` | Tests for `check_convergence.py` |
| `test_cursor_agents_continue.py` | Tests for the cursor-agents-continue toolset |
| `test_reflow_skill_md.py` | Tests for `reflow_skill_md.py` |
| `caller-window-pid.ps1` | Gets the PID of the calling terminal window |
| `cursor-agents-continue.ahk` | AutoHotkey script to advance Cursor agent prompts |
| `cursor-agents-continue.cmd` | CMD wrapper for the AHK script |
| `cursor-agents-continue-stop-others.ps1` | Stops other Cursor agents before advancing one |
| `cursor-agents-continue-caller.cmd` | Caller-side CMD wrapper |

## Subdirectories

| Directory | Role |
|---|---|
| `pr_converge_scripts_constants/` | Script-specific constants (re-exports skill constants plus adds reflow/CLI constants) |

## Conventions

- Scripts import constants from `pr_converge_scripts_constants.pr_converge_constants`, which re-exports everything from `pr_converge_skill_constants.constants`.
- Run scripts as `python ~/.claude/skills/pr-converge/scripts/<script>.py --owner <O> --repo <R> --pr-number <N>`.
- The `reflow_skill_md.py` script targets `SKILL.md` in the parent skill directory (resolved via `TARGET_SKILL_PATH` in `pr_converge_scripts_constants/reflow_skill_md_constants.py`).
