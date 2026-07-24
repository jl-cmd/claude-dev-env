# scripts

Python scripts invoked at runtime by the PR-loop skills. Each script is a standalone CLI entry point. Named constants live in pr_loop_shared_constants/ and skills_pr_loop_constants/.

## Gate, permissions, and reviewer scripts

| File | Purpose |
|---|---|
| preflight.py | Pre-flight check run before each audit loop tick |
| preflight_self_heal.py | Clears stale core.hooksPath overrides that Git seeds into fresh worktree local config |
| post_audit_thread.py | Posts an audit review (APPROVE / REQUEST_CHANGES) to a draft PR via the GitHub reviews API |
| grant_project_claude_permissions.py | Writes idempotent allow-rules and dditionalDirectories into ~/.claude/settings.json |
| 
evoke_project_claude_permissions.py | Removes the allow-rules and entries that the grant script wrote |
| stale_worktree_rule_sweep.py | Drops allow/deny rules pointing at deleted worktree directories |
| code_rules_gate.py | Pre-commit gate that runs code_rules_enforcer checks on staged Python files |
| 	erminology_sweep.py | Flags a prose term that near-misses an identifier on added code lines of a unified diff |
| 
eviews_disabled.py | Shared helper for the reviewer opt-out and opt-in gates |
| copilot_quota.py | Copilot premium-request quota pre-check |
| 
eviewer_availability.py | Unified reviewer-availability entry point for Copilot and Bugbot |
| ix_hookspath.py | Repairs a malformed core.hooksPath global git config entry |
| _claude_permissions_common.py | Internal helpers shared by the grant/revoke scripts |

## Loop state and portable-driver scripts

| File | Role |
|---|---|
| uild_audit_prompt.py | Assembles the audit agent prompt from loop state and category constants |
| uild_fix_prompt.py | Assembles the fix agent prompt from loop state and findings XML |
| init_loop_state.py | Initializes the per-PR loop-state.json file in the workspace directory |
| write_audit_outcomes.py | Writes per-loop audit outcome XML into the workspace |
| write_fix_outcomes.py | Writes per-loop fix outcome XML into the workspace |
| preflight_worktree.py | Verifies the working directory is a healthy git worktree for the target PR |
| 	eardown_worktrees.py | Removes per-PR worktrees after a clean loop exit |
| write_handoff.py | Writes durable resume-handoff files under the run directory |
| select_converge_pacer.py | Selects workflow, schedule_wakeup, or portable for pr-converge / autoconverge |
| uild_converge_task_list.py | Step-1 task list: runnable review gates plus final clean-same-head gate |
| portable_converge_driver.py | portable_converge_driver phase machine |
| _path_resolver.py | Resolves workspace and worktree paths from PR metadata |
| _cli_utils.py | Shared CLI argument parsing helpers |
| _xml_utils.py | XML serialization helpers for outcome files |

## Subdirectories

| Entry | Description |
|---|---|
| code_rules_gate_parts/ | Decomposed modules for code_rules_gate.py |
| pr_loop_shared_constants/ | Named constants for gate/permission/reviewer scripts |
| skills_pr_loop_constants/ | Named constants for loop-state and portable-driver scripts |
| 	ests/ | pytest suite for the gate/permission/reviewer scripts |

## Running tests

`ash
python -m pytest packages/claude-dev-env/skills/_shared/pr-loop/scripts/tests/
python -m pytest packages/claude-dev-env/skills/_shared/pr-loop/scripts/test_*.py
`
