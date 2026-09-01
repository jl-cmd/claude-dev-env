# _shared/pr-loop/scripts

Python scripts invoked at runtime by the PR-loop skills. Each script is a standalone CLI entry point; `pr_loop_shared_constants/` holds the named constants they import.

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
| `reviews_disabled.py` | Shared helper for the reviewer opt-out and opt-in gates; parses `CLAUDE_REVIEWS_DISABLED` tokens `bugteam`, `bugbot`, `copilot`, and `codex`, plus `CLAUDE_REVIEWS_ENABLED` for opt-in. `bugbot`, `bugteam`, and `codex` are off by default and each runs only when `CLAUDE_REVIEWS_ENABLED` lists it; `copilot` runs by default and stops only when `CLAUDE_REVIEWS_DISABLED` lists it |
| `copilot_quota.py` | Copilot premium-request quota pre-check: resolves a configured GitHub account, reads its remaining `premium_interactions` quota via `gh api copilot_internal/user`, and exits 0 (run Copilot) or non-zero (skip: out of quota, API down, or no account configured) |
| `reviewer_availability.py` | Unified reviewer-availability entry point for Copilot and Bugbot: reuses `copilot_quota.py` and `reviews_disabled.py` and exits 0 when the named `--reviewer` may be spawned, non-zero when it is opted out or (for Copilot) out of quota |
| `fix_hookspath.py` | Repairs a malformed `core.hooksPath` global git config entry |
| `_claude_permissions_common.py` | Internal helpers shared by the grant/revoke scripts: atomic settings.json writes, list mutation, path helpers |
| `check_convergence.py` | Single convergence gate check for autoconverge finalize and mark-ready hooks |
| `check_bugbot_ci.py` | Bugbot CI check-run status on a given SHA |
| `check_convergence_availability.py` | Reviewer waiver resolution for convergence gates |
| `check_convergence_gates.py` | GitHub REST leaf checks for convergence gates |
| `check_convergence_thread_gates.py` | GitHub GraphQL and REST thread gate checks |
| `check_pending_reviews.py` | Pending review requests and reviewer states |
| `fetch_copilot_reviews.py` | Copilot reviews filtered to the current HEAD |
| `post_fix_reply.py` | Inline reply poster for review comment threads |
| `run_codex_review.py` | Codex review capture wrapper for the autoconverge Codex gate |
| `codex_usage_probe.py` | Weekly Codex usage probe for gate threshold decisions |
| `codex_down_classifier.py` | Maps Codex run outcomes to completed or codex_down |
| `parse_codex_findings.py` | Parses Codex reviewer output into findings |

## Subdirectories

| Entry | Description |
|---|---|
| `code_rules_gate_parts/` | The decomposed modules `code_rules_gate.py` wires together: enforcer loading, git file sets, blob readers, added-line maps, violation scoping, wrapper plumb-through, gate running, staged-test running, and argument parsing |
| `pr_loop_shared_constants/` | Named constants used by the scripts above |
| `pr_converge_skill_constants/` | Bot logins, review states, and API templates for convergence scripts |
| `pr_converge_scripts_constants/` | CLI and reflow constants for convergence scripts |
| `codex_review_scripts_constants/` | Constants for Codex review capture and classification |
| `tests/` | pytest suite for all scripts in this directory |

## Running tests

```bash
python -m pytest packages/claude-dev-env/_shared/pr-loop/scripts/tests/
```
