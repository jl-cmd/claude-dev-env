# _shared/pr-loop/scripts/tests

pytest suite for the scripts and constants in `_shared/pr-loop/scripts/`. Each test file covers one script or one constants module.

## Test files

| File | Covers |
|---|---|
| `test__claude_permissions_common.py` | Internal helpers in `_claude_permissions_common.py` (legacy underscore prefix) |
| `test_claude_permissions_common.py` | Public API of `_claude_permissions_common.py` |
| `test_claude_permissions_constants.py` | `pr_loop_shared_constants/claude_permissions_constants.py` |
| `test_claude_settings_keys_constants.py` | `pr_loop_shared_constants/claude_settings_keys_constants.py` |
| `test_code_rules_gate.py` | `code_rules_gate.py` gate logic |
| `test_terminology_sweep.py` | `terminology_sweep.py` near-miss detection and exit codes |
| `test_code_rules_gate_constants.py` | `pr_loop_shared_constants/code_rules_gate_constants.py` |
| `test_fix_hookspath.py` | `fix_hookspath.py` repair logic |
| `test_fix_hookspath_constants.py` | `pr_loop_shared_constants/fix_hookspath_constants.py` |
| `test_grant_project_claude_permissions.py` | `grant_project_claude_permissions.py` end-to-end |
| `test_post_audit_thread.py` | `post_audit_thread.py` review-posting flow |
| `test_post_audit_thread_constants.py` | `pr_loop_shared_constants/post_audit_thread_constants.py` |
| `test_preflight.py` | `preflight.py` pre-flight checks |
| `test_preflight_constants.py` | `pr_loop_shared_constants/preflight_constants.py` |
| `test_preflight_self_heal.py` | `preflight_self_heal.py` hooks-path repair |
| `test_reviews_disabled.py` | `reviews_disabled.py` opt-out gate parsing |
| `test_copilot_quota.py` | `copilot_quota.py` end-to-end: account resolution, premium-quota classification, exit codes, and skip logging |
| `test_copilot_quota_constants.py` | `pr_loop_shared_constants/copilot_quota_constants.py` |
| `test_reviewer_availability.py` | `reviewer_availability.py` end-to-end: Copilot and Bugbot availability, opt-out via `CLAUDE_REVIEWS_DISABLED`, and every Copilot quota outcome |
| `test_reviewer_availability_constants.py` | `pr_loop_shared_constants/reviewer_availability_constants.py` |
| `test_revoke_project_claude_permissions.py` | `revoke_project_claude_permissions.py` end-to-end |
| `test_agent_config_carveout.py` | Agent-config deny-rule carve-out logic |
| `conftest.py` | Shared pytest fixtures |

## Fixtures

`fixtures/copilot_internal_user_jonecho.json` — a captured `gh api
copilot_internal/user` response driving `test_copilot_quota.py`.

## Running

```bash
python -m pytest packages/claude-dev-env/_shared/pr-loop/scripts/tests/
```
