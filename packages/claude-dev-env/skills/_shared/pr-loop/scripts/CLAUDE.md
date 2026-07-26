# scripts

Python scripts invoked at runtime by the PR-loop skills. Each script is a standalone CLI entry point. Both `bugteam` and `pr-converge` invoke these scripts during each loop tick.

## Key scripts

| File | Purpose |
|---|---|
| `preflight.py` | Pre-flight check run before each audit loop tick: verifies hooks path, finds test files, runs pytest, checks for `BUGTEAM_PREFLIGHT_SKIP` opt-out |
| `preflight_self_heal.py` | Clears stale `core.hooksPath` overrides that Git seeds into fresh worktree local config; called from `preflight.py` |
| `post_audit_thread.py` | Posts an audit review (APPROVE / REQUEST_CHANGES) to a draft PR via the GitHub reviews API; reads the body skeleton from `audit-reply-template.md` at runtime |
| `grant_project_claude_permissions.py` | Writes idempotent allow-rules and `additionalDirectories` entries into `~/.claude/settings.json` so subagents can edit the project's `.claude/` tree without prompting |
| `revoke_project_claude_permissions.py` | Removes the allow-rules and entries that `grant_project_claude_permissions.py` wrote; safe to run when no prior grant exists |
| `stale_worktree_rule_sweep.py` | Drops allow/deny rules pointing at deleted `~/.claude/worktrees/<repo>/<worktree>` directories and deduplicates the rule arrays; run by the grant and revoke flows before they write |
| `code_rules_gate.py` | Pre-commit gate that runs `code_rules_enforcer` checks on staged Python files before a fix commit lands, and the terminology sweep over the staged diff |
| `terminology_sweep.py` | Flags a prose term that near-misses an identifier introduced on added code lines of a unified diff (shared leading word, divergent tail) |
| `reviews_disabled.py` | Shared helper for the reviewer opt-out and opt-in gates; parses `CLAUDE_REVIEWS_DISABLED` tokens `bugteam`, `bugbot`, `copilot`, and `codex`, plus `CLAUDE_REVIEWS_ENABLED` for bugbot opt-in (bugbot is off by default and runs only when `CLAUDE_REVIEWS_ENABLED` lists it) |
| `copilot_quota.py` | Copilot premium-request quota pre-check: resolves a configured GitHub account, reads its remaining `premium_interactions` quota via `gh api copilot_internal/user`, and exits 0 (run Copilot) or non-zero (skip: out of quota, API down, or no account configured) |
| `reviewer_availability.py` | Unified reviewer-availability entry point for Copilot and Bugbot: reuses `copilot_quota.py` and `reviews_disabled.py` and exits 0 when the named `--reviewer` may be spawned, non-zero when it is opted out or (for Copilot) out of quota |
| `fix_hookspath.py` | Repairs a malformed `core.hooksPath` global git config entry |
| `_claude_permissions_common.py` | Internal helpers shared by the grant/revoke scripts: atomic settings.json writes, list mutation, path helpers |
| `build_audit_prompt.py` | Assembles the audit agent prompt from loop state and category constants. |
| `build_fix_prompt.py` | Assembles the fix agent prompt from loop state and findings XML. |
| `init_loop_state.py` | Initializes the per-PR `loop-state.json` file in the workspace directory. |
| `write_audit_outcomes.py` | Writes per-loop audit outcome XML into the workspace. |
| `write_fix_outcomes.py` | Writes per-loop fix outcome XML into the workspace. |
| `preflight_worktree.py` | Verifies the working directory is a healthy git worktree for the target PR's repo. Supports `--mode strict` to abort when the repo does not match. |
| `teardown_worktrees.py` | Removes per-PR worktrees after a clean loop exit. |
| `write_handoff.py` | Writes durable resume-handoff files under the run's `~/.claude/runtime/pr-loop` directory at each converge checkpoint. |
| `select_converge_pacer.py` | Selects `workflow`, `schedule_wakeup`, or `portable` for pr-converge / autoconverge from host tool flags. |
| `build_converge_task_list.py` | Step-1 task list: runnable review gates + final all_runnable_reviews_clean_same_head. |
| `portable_converge_driver.py` | portable_converge_driver phase machine: open-run and post-step transitions emit JSON next/commands only. |
| `_path_resolver.py` | Resolves workspace and worktree paths from PR owner, repo, and number. |
| `_cli_utils.py` | Shared CLI argument parsing helpers (argparse wrappers). |
| `_xml_utils.py` | XML serialization helpers for outcome files. |

## Subdirectories

| Entry | Description |
|---|---|
| `code_rules_gate_parts/` | The decomposed modules `code_rules_gate.py` wires together: enforcer loading, git file sets, blob readers, added-line maps, violation scoping, wrapper plumb-through, gate running, staged-test running, and argument parsing |
| `pr_loop_shared_constants/` | Named constants used by the gate, preflight, permissions, and review-posting scripts |
| `skills_pr_loop_constants/` | Named constants used by the loop-state, prompt-building, pacer, and handoff scripts |
| `tests/` | pytest suite for the scripts that keep their tests in a `tests/` subdirectory |

## Tests

Scripts in this directory carry their tests two ways: a paired sibling test file (`test_build_audit_prompt.py`, `test_build_fix_prompt.py`, and so on) and the `tests/` subdirectory suite. Run either from the repo root.

```bash
python -m pytest packages/claude-dev-env/skills/_shared/pr-loop/scripts/
```
