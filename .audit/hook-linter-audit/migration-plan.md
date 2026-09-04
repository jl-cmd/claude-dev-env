# Zero blocking hooks migration plan

## Target state

No Claude, Codex, Cursor-imported, or native Git hook denies an action. Linters can fail their own command. Required continuous integration checks can fail a pull request. Product permissions can require approval for destructive or external actions.

Lifecycle handlers can remain when the event is their actual input. They stay bounded and nonblocking. They do not make policy decisions.

## Static source and document checks

Move these checks into one changed-file linter. Run the linter in the editor and required continuous integration:

- `validators.run_all_validators`
- `validation/hook_format_validator.py`
- `blocking/code_rules_enforcer.py`
- `blocking/tdd_enforcer.py`
- `blocking/windows_rmtree_blocker.py`
- `blocking/duplicate_rmtree_helper_blocker.py`
- `blocking/state_description_blocker.py`
- `blocking/subprocess_budget_completeness.py`
- `blocking/hook_prose_detector_consistency.py`
- `blocking/workflow_substitution_slot_blocker.py`
- `blocking/open_questions_in_plans_blocker.py`
- `blocking/docstring_rule_gate_count_blocker.py`
- `blocking/plain_language_blocker.py` for stored prompt files
- `lifecycle/config_change_guard.py` as a file-based settings audit
- `validation/mypy_validator.py` through the normal Mypy command

Run these repository-wide checks in required continuous integration:

- `blocking/claude_md_orphan_file_blocker.py`
- `blocking/package_inventory_stale_blocker.py`
- `blocking/env_var_table_code_drift_blocker.py`
- `blocking/pytest_testpaths_orphan_blocker.py`
- secret and personal-data scanning for tracked content
- full custom code-rule validation
- Ruff
- Mypy
- JavaScript and TypeScript lint and format checks
- instruction-pair validation

The new linter supports changed files, staged files, a base revision, JSON output, and editor diagnostics. It uses one check registry. Hook wrappers do not own rules.

## Explicit workflow commands

Move these policies into the command that owns the action:

- Test preflight moves into the test runner.
- Session staging completeness moves into an explicit commit check.
- Pull-request body and volatile-path checks move into `cde pr create`.
- GitHub author selection moves into a scoped `cde pr create` process. It does not switch global account state.
- NAS connection rules move into the approved SSH wrapper and SSH configuration.
- Everything and Zoekt routing moves into the search skill or command router.
- Worktree prefetch moves into the worktree creation command.
- Skill sync moves into install and update commands.
- Session cache cleanup moves into a bounded maintenance command.
- Submodule parent updates move into an explicit sync command. A post-commit hook does not create a hidden parent commit.

## Product and service controls

These checks are not linters:

- Destructive commands use the host sandbox, native approval policy, and scoped filesystem tools.
- External posts use product data-loss prevention or the scoped pull-request command.
- Sensitive files use filesystem permissions, secret storage, and tracked-content scanning.
- Direct commits and pushes to protected branches use GitHub rulesets.
- Pull-request title and readiness rules use required GitHub checks.
- Ask-user and send-file payload shape uses product schema validation.
- Scheduler state validation belongs in the scheduler.
- Model and service-tier selection belongs in agent configuration.

Remove the corresponding blocking hooks only after the replacement control passes a live proof.

## Delete without replacement

Delete these policy hooks because they enforce a preference, duplicate another owner, or inspect prose intent:

- `blocking/write_existing_file_blocker.py`
- `blocking/gh_body_arg_blocker.py`
- `blocking/shell_substitution_blocker.py`
- `blocking/piped_pytest_blocker.py`
- `blocking/cursor_cli_python_misfire_blocker.py`
- `blocking/unscoped_search_blocker.py`
- `blocking/pr_description_writer_gate.py`
- `blocking/bot_mention_comment_blocker.py`
- `blocking/fable_spawn_gate.py`
- `blocking/luna_fast_mode_gate.py`
- `blocking/question_to_user_enforcer.py`
- `blocking/session_handoff_blocker.py`
- `blocking/send_user_file_open_locally_blocker.py`
- `blocking/stale_comment_reference_blocker.py`
- `blocking/gh_pr_author_restore.py` after author selection becomes process-scoped

Delete these wrappers after their children move:

- `blocking/pre_tool_use_dispatcher.py`
- `blocking/bash_pre_tool_use_dispatcher.py`
- `blocking/stop_dispatcher.py`
- `validation/post_tool_use_dispatcher.py`
- `blocking/bash_post_call_dispatcher.py`

## Keep only as nonblocking lifecycle work

Keep these only when a current consumer uses their result:

- worktree creation and removal
- Model Context Protocol session lifecycle
- attention notification
- instruction-load logging
- test-failure recording
- session edit tracking
- investigation tracking
- pull-request reminder
- refactor and migration advisories
- auto-formatting through editor format-on-save or an explicit format command

Each retained handler has an internal deadline. A failure cannot deny or block the host event. Logging is size-bounded and rotates.

Delete reminder hooks when an instruction, skill, or task list already owns the same message:

- `session/style_reminder_prompt.py`
- `session/task_tool_prompt.py`
- `session/working_style_prompt.py`
- `session/orchestrator_auto_starter.py`
- `session/issue_tracker_session_starter.py`

## Delivery order

1. Land the static inventory and lifecycle catalog.
2. Prune installed duplicates, missing targets, stale registries, and unmanaged retired hooks.
3. Extract file-local and repository-wide checks behind one linter command.
4. Add editor diagnostics and required continuous integration checks.
5. Add pull-request, branch, scheduler, model, search, SSH, and test command owners.
6. Prove sandbox, approval, and outbound-data controls on the real product path.
7. Remove all deny, block, and ask decisions from hook registrations.
8. Remove blocking native Git hooks and the global `core.hooksPath` installation.
9. Reinstall Claude and Codex projections. Verify exact readback.

## Acceptance checks

- The canonical inventory reports 32 direct commands and 43 hosted entries before migration.
- The lifecycle catalog has one decision for every effective hook.
- Required continuous integration runs all deterministic rules.
- Installed Claude and Codex configuration has no missing targets and no duplicate effective executions.
- No registered hook can emit `deny`, `block`, or `ask`.
- No native pre-commit or pre-push hook blocks Git.
- Destructive-command, tracked-secret, outbound-personal-data, protected-branch, and pull-request checks pass through their replacement controls.
- An editor edit gets diagnostics. A hook does not deny the edit.
