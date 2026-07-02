# hooks/hooks_constants

Shared constant modules imported by hooks throughout the `hooks/` tree. Each file holds the tunables for one hook or one cross-cutting concern, keeping magic values out of the hook scripts themselves.

## Files

| File | What it holds |
|---|---|
| `__init__.py` | Package marker (`# pragma: no-tdd-gate`) |
| `any_type_config.py` | Config for the `Any`-type escape-hatch check |
| `banned_identifiers_constants.py` | The set of banned short identifiers and banned function-name prefixes |
| `blocking_check_limits.py` | Max issue counts and preview lengths for blocking hooks |
| `bot_mention_comment_blocker_constants.py` | Patterns for detecting bot @-mentions in PR comments |
| `claude_md_orphan_file_blocker_constants.py` | Table patterns, file extensions, scan budget, and block-message text for the CLAUDE.md orphan-file blocker |
| `code_rules_enforcer_constants.py` | File-extension sets, test-path patterns, advisory line thresholds, boolean-name prefixes |
| `env_var_table_code_drift_constants.py` | Table patterns, env-var-name and code-file recognizers, scan budget, and block-message text for the env-var-table code-drift blocker |
| `code_rules_path_utils_constants.py` | Path-matching helpers used by the code-rules check modules |
| `code_verifier_spawn_preflight_gate_constants.py` | Subagent type, merge-tree command flags, timeouts, and deny-message text for the code-verifier spawn pre-flight gate |
| `command_dispatch_constants.py` | Command-word regex, command-key access pattern, tokenization pattern, and anchors for the unanchored command-dispatch meta-gate |
| `convergence_branch_constants.py` | Branch and worktree naming patterns for the convergence gate |
| `conventional_pr_title_gate_constants.py` | Bash tool name, gh executable basenames and pr create/edit subcommand tokens, title/repo flag names, semantic-title-CI workflow markers, the Conventional Commits type list and title pattern, the semantic-pull-request action `types:` input pattern, and block-message text for the conventional-PR-title gate |
| `dead_argparse_argument_constants.py` | Patterns for detecting unused argparse arguments |
| `dead_config_field_constants.py` | Patterns for detecting unused `*Config` / `*Selectors` dataclass fields |
| `dead_dataclass_field_constants.py` | Patterns for detecting unused dataclass fields |
| `dead_module_constant_constants.py` | Patterns for detecting unexported `UPPER_SNAKE` constants in `*_constants.py` modules |
| `destructive_command_segment_constants.py` | The list of destructive shell command patterns the blocker matches |
| `doc_gist_auto_publish_constants.py` | Sentinel marker and URL patterns for the doc-gist auto-publish hook |
| `docstring_rule_gate_count_blocker_constants.py` | Target rule basename, spelled-out-number lookup, count-clause and `check_*` validator patterns, and block-message text for the docstring-rule gate-count staleness blocker |
| `duplicate_function_body_constants.py` | Hashing and comparison config for the duplicate-body check |
| `duplicate_rmtree_helper_blocker_constants.py` | Sanctioned Windows-safe rmtree helper names, the definition pattern, and the exempt-path set for the duplicate-rmtree-helper blocker |
| `dynamic_stderr_handler.py` | `DynamicStderrHandler` — a logging handler that resolves `sys.stderr` at emit time (for testability) |
| `gh_pr_author_swap_constants.py` | Constants for the PR-author swap enforcement hooks |
| `hardcoded_user_path_constants.py` | Patterns for detecting hardcoded home-directory paths |
| `hook_block_logger.py` | `log_hook_block()` — shared fail-safe logger every blocking hook calls to append a JSON record of each block decision to `~/.claude/logs/hook-blocks.log` |
| `hook_log_extractor_constants.py` | Neon table name, offset state file path, timeouts, and outcome-type mapping for the hook-log extractor |
| `hook_prose_detector_consistency_constants.py` | Trigger patterns and corrective messages for the hook-prose consistency checker |
| `html_companion_constants.py` | Blocked URL schemes and other config for the `.md`-to-`.html` companion hook |
| `inline_tuple_string_magic_constants.py` | Patterns for detecting magic strings in inline tuple literals |
| `js_conventions_constants.py` | Banned identifier set, boolean-prefix pattern, and declaration/JSDoc patterns for the JavaScript convention checks |
| `md_to_html_blocker_constants.py` | Path exemptions and trigger patterns for the markdown-to-html blocker |
| `messages.py` | Short user-facing notice strings shown when a Stop hook redirects agent behavior |
| `multi_edit_reconstruction.py` | `apply_edits()` / `edits_for_tool()` — shared helpers that reconstruct the post-edit content of an Edit or MultiEdit, imported by the blockers that judge post-edit content |
| `open_questions_in_plans_blocker_constants.py` | Patterns for detecting unresolved open questions in plan documents |
| `orphan_css_class_constants.py` | Scan radius and selector patterns for the orphan-CSS-class check |
| `package_inventory_stale_blocker_constants.py` | Inventory document names, production code extensions, backtick token pattern, smallest inventory size, exempt names, scan budget, and block-message text for the package-inventory stale-entry blocker |
| `paired_test_coverage_constants.py` | Test-directory name, stem-test filename affixes, test-file globs, exempt public-function names, scan budget, coverage threshold, and guidance text for the public-function paired-test coverage check |
| `path_rewriter_constants.py` | Path rewriting patterns for the Everything-search path rewriter |
| `plain_language_blocker_constants.py` | The list of heavy words and their everyday replacements |
| `pr_converge_bugteam_enforcer_constants.py` | State keys and timing config for the bugteam-parallel enforcer |
| `pr_converge_bugteam_enforcer_state.py` | State-file helpers for the bugteam enforcer |
| `pr_description_enforcer_constants.py` | PR-description shape rules and command patterns |
| `pre_tool_use_stdin.py` | `read_hook_input_dictionary_from_stdin()` — shared stdin parser for PreToolUse hooks |
| `precommit_code_rules_gate_constants.py` | Scope argument and exit-code constants for the precommit gate |
| `project_paths_reader.py` | Loads `~/.claude/project-paths.json` — the per-user project-path registry |
| `pytest_testpaths_orphan_blocker_constants.py` | Marker filename, section and key names, test-file pattern, search budget, and block-message text for the pytest unregistered-test-directory blocker |
| `send_user_file_open_locally_blocker_constants.py` | Tool name, proactive status, and the block message for the open-locally attach blocker |
| `session_env_cleanup_constants.py` | Stale-age threshold and directory names for the session-env cleanup hook |
| `session_handoff_blocker_constants.py` | Trigger phrases for the session-handoff blocker |
| `setup_project_paths_constants.py` | Encoding policy, BOM marker, and registry meta-key used across multiple hooks |
| `state_description_blocker_constants.py` | The set of historical/comparative phrases the state-description blocker rejects |
| `stuttering_check_config.py` | Config for the stuttering (repeated-phrase) check |
| `stuttering_import_binding_constants.py` | Import-binding patterns for the stuttering check |
| `subprocess_budget_completeness_constants.py` | Required argument names for the subprocess-budget completeness check |
| `sys_path_insert_constants.py` | Patterns for detecting unguarded `sys.path.insert` calls |
| `text_stripping.py` | `strip_code_and_quotes()` — shared helper that removes fenced code blocks, inline code, and blockquotes from prose, imported by the Stop-hook prose blockers |
| `unused_module_import_constants.py` | Patterns for detecting unused module-level imports |
| `windows_rmtree_blocker_constants.py` | The unsafe `shutil.rmtree` pattern and the safe replacement pattern |
| `workflow_substitution_slot_blocker_constants.py` | Per-iteration token patterns for the workflow-slot blocker |

## Conventions

- Every file in this package is a pure constants module — no side effects, no I/O.
- Hooks import from this package with `from hooks_constants.<module> import <CONSTANT>`.
- Tests for these modules live beside them as `test_<module>.py`. Run with `python -m pytest hooks_constants/test_<name>.py`.
- `dynamic_stderr_handler.py`, `pre_tool_use_stdin.py`, `multi_edit_reconstruction.py`, and `text_stripping.py` are utility modules (not pure constants) but live here because they are shared across many hooks.
