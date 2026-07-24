# hooks/blocking

PreToolUse hooks that deny (block) tool calls when a rule is violated. The main enforcer is `code_rules_enforcer.py`, which routes each Write/Edit through a suite of focused check modules. Every other file in this directory is either a standalone blocker, a check module, or a test.

## Subdirectory

| Directory | Role |
|---|---|
| `config/` | Shared constants for the verified-commit gate family (`verified_commit_constants.py`) |
| `tdd_enforcer_parts/` | Concern modules the `tdd_enforcer.py` entry hook wires together: path classification, content analysis, candidate-path resolution, freshness, git-tracking restore detection, decisions, and constants |
| `verified_commit_gate_parts/` | Concern modules the `verified_commit_gate.py` entry hook wires together: command tokenization, directory-change resolution, gated git-invocation resolution, deny-reason resolution, and deny-payload assembly |
| `code_review_stamp_write_blocker_parts/` | Concern modules the `code_review_stamp_directory_write_blocker.py` entry hook wires together: the split directory-change-into-stamp matcher and the obfuscated-stamp-path-write matcher |
| `claude_md_orphan_file_blocker_parts/` | Concern modules the `claude_md_orphan_file_blocker.py` entry hook wires together: reference extraction, subtree scan, scan plan, decision, and constants |
| `package_inventory_stale_blocker_parts/` | Concern modules the `package_inventory_stale_blocker.py` entry hook wires together: inventory detection, decision, and constants |
| `inventory_intent_records/` | The shared per-session pending-intent store both inventory blockers read to break the file/row add-order deadlock |
| `pii_prevention_blocker_parts/` | Concern modules the `pii_prevention_blocker.py` entry hook wires together: per-repository scan exemption, the per-repository allowlist of exact values a commit may carry, and resolving the repository a commit command targets (with `config/` for the resolution deny-message constants) |
| `tests/` | pytest suite for `pii_prevention_blocker.py` repository resolution and the `pii_prevention_blocker_parts` modules |

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
| `code_rules_command_dispatch.py` | A `hooks/blocking/` command classifier matching a multi-word command regex without a start anchor or first-word tokenization |
| `code_rules_comments.py` | No new inline comments; advisory on deletion of existing ones |
| `code_rules_constants_config.py` | Constants must live in `config/`; file-global constant use-count |
| `code_rules_dead_argparse_argument.py` | Argparse arguments with no references in the same file |
| `code_rules_dead_config_field.py` | `*Config` / `*Selectors` dataclass fields with no live references |
| `code_rules_dead_dataclass_field.py` | Dataclass fields with no consuming references |
| `code_rules_dead_module_constant.py` | `UPPER_SNAKE` constants in `*_constants.py` modules with no importers |
| `code_rules_dead_split_branch.py` | A conditional whose falsy branch is unreachable because the tested value comes from a separator `str.split()`, which never returns an empty list |
| `code_rules_docstrings.py` | Google-style docstrings; `Args:` section matches signature; fallback-branch coverage |
| `code_rules_duplicate_body.py` | A function body copied from a sibling module, or a helper body inlined as a block inside a larger function in the same file |
| `code_rules_imports_logging.py` | Imports at top of file; logging format-arg style; printf tokens in `str.format`-logger messages |
| `code_rules_js_conventions.py` | Boolean-prefix naming and banned identifiers for JavaScript/TypeScript declarations and `@param {boolean}` JSDoc, scoped to changed lines |
| `code_rules_magic_values.py` | No magic numbers or strings in production code bodies |
| `code_rules_mock_completeness.py` | Mock calls that skip required arguments |
| `code_rules_naming_collection.py` | Collection names must use `all_*` prefix |
| `code_rules_optional_params.py` | No optional parameters where a required one would do |
| `code_rules_orphan_css_class.py` | CSS class attributes in Python markup with no matching `.<class>` selector |
| `code_rules_paired_test.py` | A public function omitted by a module's established paired test suite must get a behavioral test — checked on both the production-module write and the stem-matched test-file write |
| `code_rules_path_utils.py` | Path utility helpers shared across check modules |
| `code_rules_paths_syspath.py` | `sys.path.insert` must be guarded |
| `code_rules_probe_chains.py` | Probe-chain detection logic |
| `code_rules_probe_detection.py` | Probe pattern detection helpers |
| `code_rules_probe_recording.py` | Probe recording utilities |
| `code_rules_scope_binding.py` | Scope/binding analysis utilities |
| `code_rules_shared.py` | Shared dataclasses and helpers used by multiple check modules |
| `code_rules_string_magic.py` | Magic string detection with masking and f-string support; whitespace-only indentation literals in function bodies |
| `code_rules_test_assertions.py` | Test assertion style rules |
| `code_rules_test_layout.py` | Dead scaffolding in a test module: a private module constant read by no other line, and an unused parameter on a private test helper |
| `code_rules_test_branching_except.py` | No bare or broad `except` in test branches |
| `code_rules_test_isolation.py` | Tests must not rely on home-dir or temp-dir side effects |
| `code_rules_type_escape.py` | No `Any` imports, `cast()`, or `# type: ignore` outside boundary files |
| `code_rules_typeddict_stub.py` | TypedDict pairs (`_encode_*`/`_decode_*`) must both exist in the same module |
| `code_rules_unused_imports.py` | Unused module-level imports |

## Other standalone blockers

| File | Event | What it blocks |
|---|---|---|
| `orchestrator_refresh_reschedule_gate.py` | PreToolUse (ScheduleWakeup/CronCreate) | `/orchestrator-refresh` re-arm when run status is not `active` |
| `agent_model_pin_blocker.py` | PreToolUse (Write/Edit/MultiEdit) | An agent-definition `.md` under `agents/` (or installed `~/.claude/agents/`) whose frontmatter pins a concrete `model:` value; an agent omits the key or sets `inherit` |
| `block_main_commit.py` | PreToolUse (Bash) | `git commit`/`git push` directly to `main` |
| `bot_mention_comment_blocker.py` | PreToolUse (Write/Edit) | PR review comments that @-mention a bot |
| `claude_md_orphan_file_blocker.py` | PreToolUse (Write/Edit/MultiEdit) | Per-directory `CLAUDE.md` table cells naming a bare filename absent from the directory subtree |
| `code_review_pr_create_gate.py` | PreToolUse (Bash/MCP GitHub) | `gh pr create` or the MCP `create_pull_request` tool without a clean `xhigh` code-review stamp covering the branch surface |
| `code_review_push_gate.py` | PreToolUse (Bash/PowerShell) | `git push` without a clean `low` code-review stamp covering the branch surface |
| `code_review_stamp_directory_write_blocker.py` | PreToolUse (Bash/PowerShell/Write/Edit/MultiEdit) | Shell or file-tool writes into `~/.claude/code-review-stamps/`, and shell references to the stamp store module or its mint call, outside the sanctioned invoker |
| `code_verifier_spawn_preflight_gate.py` | PreToolUse (Agent) | Spawning the `code-verifier` subagent when the branch has a merge conflict vs its base or a CODE_RULES violation on a working-tree-added line, or the CODE_RULES engine fails to load |
| `convergence_gate_blocker.py` | PreToolUse (Bash) | Convergence workflow actions on a conflicting PR |
| `conventional_pr_title_gate.py` | PreToolUse (Bash) | `gh pr create`/`gh pr edit` with a `--title` that is not a Conventional Commit, in a repo whose CI runs a semantic-pull-request title check |
| `destructive_command_blocker.py` | PreToolUse (Bash/PowerShell) | Shell commands with destructive literals (`rm -rf`, `git reset --hard`, etc.) |
| `docstring_rule_gate_count_blocker.py` | PreToolUse (Write/Edit/MultiEdit) | A stale spelled-out gate-validator count in `docstring-prose-matches-implementation.md` — the "N more gate validators" / "M gated slices" count drifting from the `check_docstring_*` validators the prose names |
| `duplicate_rmtree_helper_blocker.py` | PreToolUse (Write/Edit) | A local re-definition of the Windows-safe rmtree helper trio (`_strip_read_only_and_retry`, `_force_remove_tree` / `force_rmtree`) in place of importing a shared helper |
| `env_var_table_code_drift_blocker.py` | PreToolUse (Write/Edit/MultiEdit) | A markdown env-var summary table row attributing an environment variable to a code file whose source never references that variable name |
| `es_exe_path_rewriter.py` | PreToolUse | Rewrites paths referencing `.exe` under the Everything search path |
| `unscoped_search_blocker.py` | PreToolUse (Bash/PowerShell) | Whole-drive or bare-home tree walks (`find /`, recursive `Get-ChildItem` on `C:\\`/`~`) |
| `gh_body_arg_blocker.py` | PreToolUse (Bash) | `gh` commands passing `--body`/`-b` directly (requires `--body-file` instead) |
| `gh_pr_author_enforcer.py` | PreToolUse | Enforces PR author identity rules |
| `gh_pr_author_restore.py` | PostToolUse | Restores PR author after a tool call |
| `hedging_language_blocker.py` | Stop | Responses with hedging words (`likely`, `probably`, `appears to`) |
| `hook_prose_detector_consistency.py` | PreToolUse (Write/Edit) | Hook docstrings/messages that claim a trigger the detector cannot fire on |
| `intent_only_ending_blocker.py` | Stop | Responses that end on a plan or intent without doing the work |
| `open_questions_in_plans_blocker.py` | PreToolUse (Write/Edit) | Plan documents with unresolved open questions |
| `nas_ssh_binary_enforcer.py` | PreToolUse (Bash) | A bare `ssh`/`scp`/`sftp` command word targeting the NAS (Git Bash's MSYS ssh stalls on an interactive password prompt), or the full `System32/OpenSSH` binary to that host without `-o BatchMode=yes` |
| `package_inventory_stale_blocker.py` | PreToolUse (Write) | A new production code file created in a directory whose `README.md`/`CLAUDE.md` inventory (or a parent skill's `SKILL.md` Layout table mapping the `scripts/` subdirectory) names two or more sibling files but no entry for the new file |
| `pii_commit_command.py` | library | Token-aware git-commit detection reused by `pii_prevention_blocker.py` |
| `pii_payload_scan.py` | library | Write/Edit and durable post-body PII evaluation reused by `pii_prevention_blocker.py` |
| `pii_prevention_blocker.py` | PreToolUse (Write/Edit/MultiEdit/Bash/PowerShell/MCP GitHub) | Entry hook — content that carries high-confidence personal data or secrets (real emails, home-dir paths, private IPs, credential material) on write, durable GitHub posts, or staged commit paths; resolves the staged-commit repository from the command it gates (via `pii_prevention_blocker_parts`), not the session working directory |
| `pii_scanner.py` | library | Pure text scanners shared by `pii_prevention_blocker.py` |
| `plain_language_blocker.py` | PreToolUse (Write/Edit/AskUserQuestion) | Heavy or jargon words in user-facing prose |
| `pr_converge_bugteam_enforcer.py` | PreToolUse | Enforces that bugteam runs in parallel with bugbot in pr-converge loops |
| `pr_description_enforcer.py` | PreToolUse (Bash) | `gh pr create`/`edit`/`comment` bodies that fail the Anthropic claude-code style audit, proof-shaped `gh pr comment` bodies missing proof-of-work parts, and `gh pr ready` while the PR carries no passing proof comment |
| `precommit_code_rules_gate.py` | PreToolUse (Bash) | Staged changes that fail the CODE_RULES gate at commit time |
| `pytest_testpaths_orphan_blocker.py` | PreToolUse (Write/Edit/MultiEdit) | New `test_*.py` files created under a directory absent from a package's explicit pytest `testpaths` allowlist |
| `question_to_user_enforcer.py` | Stop | User-directed questions not routed through `AskUserQuestion` |
| `reviewer_spawn_gate.py` | PreToolUse (Bash) | A sentinel-marked autoconverge reviewer-spawn command (Copilot review request, Bugbot rerun comment) run while `reviewer_availability.py` reports that reviewer down or out of quota |
| `send_user_file_open_locally_blocker.py` | PreToolUse (SendUserFile) | A desk-side file attach (`SendUserFile` with `status` not `proactive`); points to opening the file locally via `Show-Asset.ps1` |
| `sensitive_file_protector.py` | PreToolUse (Write/Edit) | Writes to sensitive credential or config files |
| `session_edit_stage_gate.py` | PreToolUse (Bash) | A `git commit` that would drop files edited this session because they are tracked but left unstaged |
| `session_handoff_blocker.py` | Stop | Responses suggesting a new session mid-task |
| `stale_comment_reference_blocker.py` | PreToolUse (Edit) | An Edit that rewrites a Python code line while keeping the standalone comment directly above it, when that comment names an identifier the rewrite removes from the line |
| `state_description_blocker.py` | PreToolUse (Write/Edit) | Historical/comparative language in documentation |
| `subprocess_budget_completeness.py` | PreToolUse | Subprocess calls missing required budget arguments |
| `tdd_enforcer.py` | PreToolUse (Write/Edit) | Production code written without a matching failing test |
| `verdict_directory_write_blocker.py` | PreToolUse (Bash/PowerShell) | Shell writes into `~/.claude/verification/` |
| `verified_commit_gate.py` | PreToolUse (Bash/PowerShell) | `git commit`/`git push` without a passing verifier verdict |
| `verified_commit_message_accuracy_blocker.py` | PreToolUse | Commit messages that misstate what the diff has |
| `verifier_verdict_minter.py` | SubagentStop | Mints a passing verdict file when a `code-verifier` agent finishes cleanly |
| `volatile_path_in_post_blocker.py` | PreToolUse (Bash/MCP GitHub) | `gh` post commands and GitHub MCP post tools whose body references a volatile path (job scratch dir, worktree, or system temp) that outlives the durable post |
| `windows_rmtree_blocker.py` | PreToolUse (Write/Edit) | `shutil.rmtree` with `ignore_errors=True` on Windows |
| `workflow_substitution_slot_blocker.py` | PreToolUse (Write/Edit) | Workflow templates with bare per-iteration tokens missing angle-bracket slots |
| `write_existing_file_blocker.py` | PreToolUse (Write) | Write to a path where a file already exists |

## Supporting modules

| File | Role |
|---|---|
| `_gh_body_arg_utils.py` | Parsing helpers for `gh_body_arg_blocker.py` |
| `code_review_enforcement_config_bootstrap.py` | Binds `config.code_review_enforcement_constants` to the sibling `config/` file by explicit location, so the code-review gate family resolves its constants regardless of a foreign `config` package's `sys.path` order |
| `code_review_gate_deny.py` | Shared deny scaffold for the push and PR-create code-review gates: the `hookSpecificOutput` deny-payload builder and the log-and-emit helper, so both gates share one deny shape |
| `code_review_stamp_store.py` | Reads and writes the per-work-tree code-review stamp files under `~/.claude/code-review-stamps/`, and decides whether a clean stamp at the needed effort covers the live branch surface |
| `pr_description_body_audit.py` | Body audit logic for `pr_description_enforcer.py` |
| `pr_description_command_parser.py` | `gh` command parsing for `pr_description_enforcer.py` |
| `pr_description_pr_number.py` | PR number extraction logic |
| `pr_description_proof_of_work.py` | Proof-of-work comment audit and `gh pr ready` gate logic for `pr_description_enforcer.py` |
| `pr_description_readability.py` | Readability checks on PR description bodies |
| `verification_verdict_store.py` | Reads and writes verdict files under `~/.claude/verification/` |
| `verified_commit_config_bootstrap.py` | Binds `config.verified_commit_constants` to the sibling `config/` file by explicit location, so the gate family resolves its constants regardless of a foreign `config` package's `sys.path` order |

## Conventions

- Tests live beside each hook as `test_<hookname>.py` or `test_<hookname>_<suffix>.py`. Run with `python -m pytest <test_file>`.
- Tunable constants live in `hooks_constants/<hook_name>_constants.py`; the verified-commit family uses `blocking/config/verified_commit_constants.py`.
