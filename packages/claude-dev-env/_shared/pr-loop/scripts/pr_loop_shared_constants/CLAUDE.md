# pr_loop_shared_constants

Named constants for every script in `_shared/pr-loop/scripts/`. Each module owns the constants for one script; the module name mirrors the script name with a `_constants` suffix.

## Modules

| File | Constants for |
|---|---|
| `claude_permissions_constants.py` | `grant_project_claude_permissions.py` and `revoke_project_claude_permissions.py` — permission rule strings and settings.json keys |
| `claude_settings_keys_constants.py` | Top-level `~/.claude/settings.json` key names used across the permission helpers |
| `code_rules_gate_constants.py` | `code_rules_gate.py` — file extensions, git diff subcommands, test filename patterns |
| `inline_duplicate_body_span_constants.py` | `code_rules_gate.py` — regex and capture-group indices for the same-file inline-duplicate message, which carries both the helper and the enclosing span the gate reconstructs the union from |
| `fix_hookspath_constants.py` | `fix_hookspath.py` — verification suffix and related strings |
| `post_audit_thread_constants.py` | `post_audit_thread.py` — HTTP status codes, retry counts, GitHub API paths |
| `preflight_constants.py` | `preflight.py` — env-var names, git subcommands, pytest exit codes, test discovery patterns |
| `preflight_self_heal_constants.py` | `preflight_self_heal.py` — git config keys and local-scope detection strings |
| `reviews_disabled_constants.py` | `reviews_disabled.py` — `CLAUDE_REVIEWS_DISABLED` token taxonomy |
| `copilot_quota_constants.py` | `copilot_quota.py` — `COPILOT_QUOTA_ACCOUNT` env-var name, `copilot_internal/user` API path, the `premium_interactions` gating field names, the four skip/run exit codes, and the default `.env` path |
| `terminology_sweep_constants.py` | `terminology_sweep.py` — identifier and prose-token regexes, diff-parsing prefixes, code-file extensions, and the finding-message template |
| `__init__.py` | Empty package marker |

## Convention

Every constant is `UPPER_SNAKE_CASE` with an explicit type annotation. No magic literals appear in the consuming scripts — all values live here. Test coverage for each module lives in `tests/test_<module_name>.py`.
