# Shared PR-loop scripts

Runnable helpers used by **bugteam**, **qbug**, **pr-converge**, and related skills. These files are **executed** from the repository (or a `~/.claude` install); they are not meant as primary model-reading context.

## Inventory

| File | Purpose |
| --- | --- |
| `preflight.py` | Local checks before a PR-loop run (pytest discovery, optional pre-commit, hooksPath sanity). |
| `code_rules_gate.py` | CODE_RULES gate over PR-scoped diffs (`--base`, staged-only, path filters). |
| `fix_hookspath.py` | Repair `core.hooksPath` when it does not point at the packaged git-hooks tree. |
| `gh_util.py` | GitHub CLI helpers (pagination-safe JSON parsing, review fetches). |
| `grant_project_claude_permissions.py` / `revoke_project_claude_permissions.py` | Claude Code permission JSON helpers used during publish-style flows. |
| `_claude_permissions_common.py` | Shared implementation for the permission scripts. |

Configuration lives under `config/` next to these scripts (for example `preflight_constants.py`, `code_rules_gate_constants.py`).

## Gate semantics

Merge-base selection, diff scoping, and exit codes for `code_rules_gate.py` are documented in [`../code-rules-gate.md`](../code-rules-gate.md).
