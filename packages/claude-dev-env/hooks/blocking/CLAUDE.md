# hooks/blocking

PreToolUse hooks that deny (block) tool calls when a rule is violated. The main enforcer is `code_rules_enforcer.py`, which routes each Write/Edit through a suite of focused check modules. Every other file in this directory is either a standalone blocker, a check module, or a test.

## Subdirectory

| Directory | Role |
|---|---|
| `config/` | Shared constants for the verified-commit gate family (`verified_commit_constants.py`) |

## Core enforcer

| File | What it does |
|---|---|
| `code_rules_enforcer.py` | Entry point — reads PreToolUse stdin, reconstructs post-edit content, dispatches all check modules, and returns a block with a per-issue list when any check fails |

The check modules it calls are the `code_rules_<concern>.py` files below.

## Check modules (imported by `code_rules_enforcer.py`)

| Module | Concern |
|---|---|
| `code_rules_annotations_length.py` | Parameter/return annotations, function length, pytest fixture annotation requirements |
| `code_rules_banned_identifiers.py` | Banned short names (`ctx`, `cfg`, `msg`, etc.), banned prefixes (`handle_`, `process_`, etc.) |
| `code_rules_boolean_mustcheck.py` | Boolean naming (`is_`/`has_`/… prefixes) and must-check return values |
| `code_rules_comments.py` | No new inline comments; no deletion of existing ones |
| `code_rules_constants_config.py` | Constants must live in `config/`; file-global constant use-count |
| `code_rules_dead_argparse_argument.py` | Argparse arguments with no references in the same file |
| `code_rules_dead_config_field.py` | `*Config` / `*Selectors` dataclass fields with no live references |
| `code_rules_dead_dataclass_field.py` | Dataclass fields with no consuming references |
| `code_rules_dead_module_constant.py` | `UPPER_SNAKE` constants in `*_constants.py` modules with no importers |
| `code_rules_docstrings.py` | Google-style docstrings; `Args:` section matches signature; fallback-branch coverage |
| `code_rules_duplicate_body.py` | Functions whose bodies match another function's body in the same file |
| `code_rules_imports_logging.py` | Imports at top of file; logging format-arg style |
| `code_rules_magic_values.py` | No magic numbers or strings in production code bodies |
| `code_rules_mock_completeness.py` | Mock calls that skip required arguments |
| `code_rules_naming_collection.py` | Collection names must use `all_*` prefix |
| `code_rules_optional_params.py` | No optional parameters where a required one would do |
| `code_rules_orphan_css_class.py` | CSS class attributes in Python markup with no matching `.<class>` selector |
| `code_rules_path_utils.py` | Path utility helpers shared across check modules |
| `code_rules_paths_syspath.py` | `sys.path.insert` must be guarded |
| `code_rules_probe_chains.py` | Probe-chain detection logic |
| `code_rules_probe_detection.py` | Probe pattern detection helpers |
| `code_rules_probe_recording.py` | Probe recording utilities |
| `code_rules_scope_binding.py` | Scope/binding analysis utilities |
| `code_rules_shared.py` | Shared dataclasses and helpers used by multiple check modules |
| `code_rules_string_magic.py` | Magic string detection with masking and f-string support |
| `code_rules_test_assertions.py` | Test assertion style rules |
| `code_rules_test_branching_except.py` | No bare or broad `except` in test branches |
| `code_rules_test_isolation.py` | Tests must not rely on home-dir or temp-dir side effects |
| `code_rules_type_escape.py` | No `Any` imports, `cast()`, or `# type: ignore` outside boundary files |
| `code_rules_typeddict_stub.py` | TypedDict pairs (`_encode_*`/`_decode_*`) must both exist in the same module |
| `code_rules_unused_imports.py` | Unused module-level imports |

## Other standalone blockers

| File | Event | What it blocks |
|---|---|---|
| `block_main_commit.py` | PreToolUse (Bash) | `git commit`/`git push` directly to `main` |
| `bot_mention_comment_blocker.py` | PreToolUse (Write/Edit) | PR review comments that @-mention a bot |
| `claude_md_orphan_file_blocker.py` | PreToolUse (Write/Edit/MultiEdit) | Per-directory `CLAUDE.md` table cells naming a bare filename absent from the directory subtree |
| `code_verifier_spawn_preflight_gate.py` | PreToolUse (Agent) | Spawning the `code-verifier` subagent when the branch has a merge conflict vs its base or a CODE_RULES violation on a working-tree-added line |
| `convergence_gate_blocker.py` | PreToolUse (Bash) | Convergence workflow actions on a conflicting PR |
| `destructive_command_blocker.py` | PreToolUse (Bash/PowerShell) | Shell commands with destructive literals (`rm -rf`, `git reset --hard`, etc.) |
| `es_exe_path_rewriter.py` | PreToolUse | Rewrites paths referencing `.exe` under the Everything search path |
| `gh_body_arg_blocker.py` | PreToolUse (Bash) | `gh` commands passing `--body`/`-b` directly (requires `--body-file` instead) |
| `gh_pr_author_enforcer.py` | PreToolUse | Enforces PR author identity rules |
| `gh_pr_author_restore.py` | PostToolUse | Restores PR author after a tool call |
| `hedging_language_blocker.py` | Stop | Responses with hedging words (`likely`, `probably`, `appears to`) |
| `hook_prose_detector_consistency.py` | PreToolUse (Write/Edit) | Hook docstrings/messages that claim a trigger the detector cannot fire on |
| `intent_only_ending_blocker.py` | Stop | Responses that end on a plan or intent without doing the work |
| `md_to_html_blocker.py` | PreToolUse (Write/Edit) | Writing `.md` files when an `.html` companion is required |
| `open_questions_in_plans_blocker.py` | PreToolUse (Write/Edit) | Plan documents with unresolved open questions |
| `package_inventory_stale_blocker.py` | PreToolUse (Write) | A new production code file created in a directory whose `README.md`/`CLAUDE.md` inventory names two or more sibling files but no entry for the new file |
| `plain_language_blocker.py` | PreToolUse (Write/Edit/AskUserQuestion) | Heavy or jargon words in user-facing prose |
| `pr_converge_bugteam_enforcer.py` | PreToolUse | Enforces that bugteam runs in parallel with bugbot in pr-converge loops |
| `pr_description_enforcer.py` | PreToolUse (Bash) | `gh pr create`/`edit` without a PR-description-writer-authored body |
| `precommit_code_rules_gate.py` | PreToolUse (Bash) | Staged changes that fail the CODE_RULES gate at commit time |
| `pytest_testpaths_orphan_blocker.py` | PreToolUse (Write/Edit/MultiEdit) | New `test_*.py` files created under a directory absent from a package's explicit pytest `testpaths` allowlist |
| `question_to_user_enforcer.py` | Stop | User-directed questions not routed through `AskUserQuestion` |
| `send_user_file_open_locally_blocker.py` | PreToolUse (SendUserFile) | A desk-side file attach (`SendUserFile` with `status` not `proactive`); points to opening the file locally via `Show-Asset.ps1` |
| `sensitive_file_protector.py` | PreToolUse (Write/Edit) | Writes to sensitive credential or config files |
| `session_handoff_blocker.py` | Stop | Responses suggesting a new session mid-task |
| `state_description_blocker.py` | PreToolUse (Write/Edit) | Historical/comparative language in documentation |
| `subprocess_budget_completeness.py` | PreToolUse | Subprocess calls missing required budget arguments |
| `tdd_enforcer.py` | PreToolUse (Write/Edit) | Production code written without a matching failing test |
| `verdict_directory_write_blocker.py` | PreToolUse (Bash/PowerShell) | Shell writes into `~/.claude/verification/` |
| `verified_commit_gate.py` | PreToolUse (Bash/PowerShell) | `git commit`/`git push` without a passing verifier verdict |
| `verified_commit_message_accuracy_blocker.py` | PreToolUse | Commit messages that misstate what the diff has |
| `verifier_verdict_minter.py` | SubagentStop | Mints a passing verdict file when a `code-verifier` agent finishes cleanly |
| `windows_rmtree_blocker.py` | PreToolUse (Write/Edit) | `shutil.rmtree` with `ignore_errors=True` on Windows |
| `workflow_substitution_slot_blocker.py` | PreToolUse (Write/Edit) | Workflow templates with bare per-iteration tokens missing angle-bracket slots |
| `write_existing_file_blocker.py` | PreToolUse (Write) | Write to a path where a file already exists |

## Supporting modules

| File | Role |
|---|---|
| `_gh_body_arg_utils.py` | Parsing helpers for `gh_body_arg_blocker.py` |
| `_md_to_html_blocker_test_support.py` | Test fixtures shared across `md_to_html_blocker` tests |
| `md_path_exemptions.py` | Path exemption logic for `md_to_html_blocker.py` |
| `pr_description_body_audit.py` | Body audit logic for `pr_description_enforcer.py` |
| `pr_description_command_parser.py` | `gh` command parsing for `pr_description_enforcer.py` |
| `pr_description_pr_number.py` | PR number extraction logic |
| `pr_description_readability.py` | Readability checks on PR description bodies |
| `verification_verdict_store.py` | Reads and writes verdict files under `~/.claude/verification/` |

## Conventions

- Tests live beside each hook as `test_<hookname>.py` or `test_<hookname>_<suffix>.py`. Run with `python -m pytest <test_file>`.
- Tunable constants live in `hooks_constants/<hook_name>_constants.py`; the verified-commit family uses `blocking/config/verified_commit_constants.py`.
- `conftest.py` gives shared pytest fixtures for the blocking test suite.
