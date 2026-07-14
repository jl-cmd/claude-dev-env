# dev_env_scripts_constants

Named constants for scripts in `scripts/`. Follows the project convention that timeouts, delays, and retries live in `timing.py`.

## Modules

| File | Constants for |
|---|---|
| `timing.py` | `sweep_empty_dirs.py` — `DEFAULT_AGE_SECONDS` (smallest age before an empty directory is eligible for removal) and `DEFAULT_POLL_INTERVAL` (seconds between sweep passes in continuous-watch mode) |
| `gh_artifact_upload_constants.py` | `gh_artifact_upload.py` — the `artifacts` release tag, title, and notes body, the GitHub CLI binary name, the asset-name timestamp format and template, the asset download URL template, the notes-file suffix, and the text encoding |
| `claude_chain_constants.py` | `claude_chain_runner.py` — the chain config filename and home subdirectory, the usage-limit signature text, the per-binary status labels, the default timeout, CLI flag and separator tokens, config JSON keys, invalid-shape reason text, config-error and exhausted-chain message templates, and CLI exit codes |
| `grok_worker_constants.py` | `grok_worker_preflight.py` and `grok_headless_runner.py` — the grok binary name and CLI flags, the auth and ping leader-socket filenames, the ping cache filename, keys, and TTL, the subprocess timeouts, the install manifest and agents-directory names, the role-to-agent-files map, the fallthrough reason strings, the stdout line templates, the exit codes, the auth-failure and usage-limit signature lists, the headless-runner leader-socket filename parts, the model pin, the post-kill grace timeout, the timeout return code, and the outcome classification labels |
| `__init__.py` | Empty package marker |

## Convention

Every constant is `UPPER_SNAKE_CASE` with an explicit type annotation and a docstring. Scripts import from here rather than embedding literal values in their bodies.
