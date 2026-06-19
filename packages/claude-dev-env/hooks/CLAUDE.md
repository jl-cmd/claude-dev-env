# hooks

Python hook scripts wired into Claude Code's lifecycle via `settings.json`. Each hook answers one or more lifecycle events (`PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, `SessionStart`, `SessionEnd`) and either blocks a tool call, annotates it, or performs a side-effect.

## Subdirectories

| Directory | Role |
|---|---|
| `advisory/` | Hooks that warn but do not block (`permissionDecision: "ask"`) |
| `blocking/` | Hooks that deny tool calls when a rule is violated |
| `blocking/config/` | Shared constants for the verified-commit gate family |
| `diagnostic/` | Hooks that record and extract hook-firing records into Neon |
| `diagnostic/migrations/` | SQL migrations for the `hook_events` Neon schema |
| `diagnostic/queries/` | Parameterized SQL queries for inspecting blocked commands |
| `git-hooks/` | Native git hooks (`pre-commit`, `pre-push`, `post-commit`) installed via the git-hooks path |
| `git-hooks/git_hooks_constants/` | Shared constants for the git-hook scripts |
| `hooks_constants/` | Shared constant modules imported by multiple hooks across this tree |
| `lifecycle/` | Hooks that run at session or config-change boundaries |
| `observability/` | PostToolUse hooks that record agent behavior for diagnostics |
| `session/` | SessionStart and SessionEnd hooks for per-session cleanup |
| `validation/` | PostToolUse hooks that validate code quality after a write (mypy, auto-format) |
| `validators/` | Library modules used by the validation hooks — checks split by concern |
| `workflow/` | PostToolUse hooks that trigger doc publishing and companion-file generation |

## Conventions

- **Event mapping:** Every hook reads JSON from stdin and exits 0 (allow) or prints a `hookSpecificOutput` block (block/ask). Blocking hooks set `permissionDecision: "block"`.
- **Constants companion:** Each hook with more than a handful of tunable strings keeps them in a `hooks_constants/<hook_name>_constants.py` sibling. Import from there; do not repeat literals.
- **Tests:** Each hook has one or more `test_<hookname>*.py` files beside it. Run with `python -m pytest <test_file>`.
- **Registration:** Hooks are declared in `settings.json` under the right lifecycle event. The installer (`packages/claude-dev-env/bin/install.mjs`) merges the hook entries during `npx claude-dev-env`.
- **Top-level utilities:** `_gh_pr_author_swap_utils.py` and `rewrite_plugin_paths.py` are shared helpers imported by multiple blocking hooks. `hooks.json` records the canonical hook-to-event mapping for auditing.
