# dev_env_scripts_constants

Named constants for scripts in `scripts/`. Follows the project convention that timeouts, delays, and retries live in `timing.py`.

## Modules

| File | Constants for |
|---|---|
| `timing.py` | `sweep_empty_dirs.py` - `DEFAULT_AGE_SECONDS` (smallest age before an empty directory is eligible for removal) and `DEFAULT_POLL_INTERVAL` (seconds between sweep passes in continuous-watch mode); `spawn_grok_batch.py` - `WORKER_STAGGER_SECONDS` (seconds between staggered headless grok worker starts); `invoke_code_review.py` - `DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS` (timeout for one headless `/code-review` chain run) |
| `gh_artifact_upload_constants.py` | `gh_artifact_upload.py` - the `artifacts` release tag, title, and notes body, the GitHub CLI binary name, the asset-name timestamp format and template, the asset download URL template, the notes-file suffix, and the text encoding |
| `claude_chain_constants.py` | `claude_chain_runner.py` - the chain config filename and home subdirectory, the usage-limit signature text, the per-binary status labels, routing-mode tokens (`usage_ranked` / `ordered_account`), outcome `terminal_status` values (`served` / `advisor_blocked` / `chain_exhausted` / `timeout`), the default timeout, CLI flag and separator tokens, config JSON keys (including optional `credentials_path`), invalid-shape reason text, config-error and exhausted-chain message templates, and CLI exit codes (including advisor-blocked); `invoke_code_review.py` and `resolve_worker_spawn.py` - the text-codec keyword names and the `collect_forwarded_text_codec` helper that forwards them to the subprocess runner for text-mode capture |
| `claude_chain_usage_constants.py` | `claude_chain_usage.py` - full weekly percent scale, usage-pause skill path segments, CLI config-path flag, JSON report keys, and probe error message templates |
| `grok_worker_constants.py` | `grok_worker_preflight.py`, `grok_headless_runner.py`, `spawn_grok_batch.py`, and `resolve_worker_spawn.py` - the `grok` binary name and CLI flags, model and subcommand tokens, leader-socket and scratch-file name parts, auth and usage-limit signature lists, outcome classifications, fallthrough reasons, tool-profile names and prompt headers, worker timeouts (default, plus the floor and the `MAXIMUM_WORKER_TIMEOUT_SECONDS` ceiling that the batch spec parse, the headless runner, and the spawn dispatcher all enforce, each bound carrying one rejection template shared by those sites, plus launch-failure return code and post-kill grace), the process-tree kill attempt limit and kill-failed classification, the preflight ping's single-turn cap, ping-cache keys and TTL, batch-spec and summary JSON keys, the prompt-part and report-stream join separators, and the CLI launch-error stderr prefix |
| `code_review_constants.py` | `invoke_code_review.py` - the `/code-review ultra --fix` prompt, opus model alias, permission-mode flag and value, result mode and JSON keys, session-model CLI flag, git dirty-check tokens, and in-session return markers |
| `__init__.py` | Empty package marker |

## Convention

Every constant is `UPPER_SNAKE_CASE` with an explicit type annotation and a docstring. Scripts import from here rather than embedding literal values in their bodies.
