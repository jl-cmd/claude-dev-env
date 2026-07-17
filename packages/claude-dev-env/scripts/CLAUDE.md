# scripts

Utility scripts installed into `~/.claude/scripts/` by `bin/install.mjs`. Each script is a standalone tool a user or hook can invoke directly.

## Scripts

| File | Purpose |
|---|---|
| `claude_chain_runner.py` | Runs a `claude` invocation through a config-driven fallback chain (`~/.claude/claude-chain.json`): the leading binary serves the call, and only a usage-limit failure falls over to the next logged-in binary; usable as an imported module (`run_claude`) or a CLI. Copy `claude-chain.example.json` to `~/.claude/claude-chain.json` and list your binaries in fallback order |
| `claude_usage_probe.py` | Thin wrapper over usage-pause `resolve_usage_window.py` for claude-review: prints `{session_utilization, weekly_utilization, weekly_near_cap, session_has_usage_left, source, probe_ok}`; never blocks on probe failure |
| `invoke_code_review.py` | Host-aware `/code-review xhigh --fix` invoker: in-session on Claude+opus, headless via `claude_chain_runner` otherwise; optional `--session-has-usage-left false` forces chain when the primary session is drained |
| `gh_artifact_upload.py` | Uploads a file to a repo's durable `artifacts` prerelease under a timestamped asset name and prints the permanent download URL a GitHub post can link |
| `grok_headless_runner.py` | Runs one worker as headless `grok`: builds argv, mints a unique leader socket, captures streams, kills on timeout with grace, classifies ok/usage_limit/auth_failure/timeout/error; imported by `spawn_grok_batch.py` |
| `grok_worker_preflight.py` | Soft gate for the headless grok tier: binary on PATH, `grok models` auth, install manifest + role agents, opt-in cached live ping; non-zero exit is fallthrough, not failure |
| `setup_project_paths.py` | One-time bootstrap: discovers git repos via `es.exe` (Everything) and writes `~/.claude/project-paths.json`; never hardcodes scan roots |
| `spawn_grok_batch.py` | Launches a fleet of headless grok workers from a JSON batch spec: gates once through the preflight, assembles each prompt from part files, staggers starts, runs each through `grok_headless_runner.py`, and emits one batch summary JSON |
| `sweep_empty_dirs.py` | Deletes empty directories older than a configurable age under a given root; runs once (`--once`) or in continuous-watch mode |
| `sync_to_cursor.py` | Entry point for syncing Claude rules to Cursor `.mdc` files; delegates to the `sync_to_cursor/` package |
| `resolve_worker_spawn.py` | Dispatches a worker role through grok then claude fallback tiers (preflight, headless grok, `claude_agent_required` handoff, optional claude headless); protocol: [`../_shared/pr-loop/worker-spawn.md`](../_shared/pr-loop/worker-spawn.md) |

## PowerShell scripts

| File | Purpose |
|---|---|
| `Audit-ShellPolicy.ps1` | Audits Bash tool calls in session transcripts against the `pwsh`-only shell policy |
| `Migrate-ShellPolicy.ps1` | Applies automated fixes for common shell-policy violations found by the audit script |
| `Install-SweepEmptyDirs.ps1` | Registers `sweep_empty_dirs.py` as a scheduled task on Windows |
| `check.ps1` | Runs the full code-quality check suite |
| `Show-Asset.ps1` | Opens files on screen, sizing each image window to the image's pixel dimensions (scaled to fit the screen); non-image files open in their default application |
| `Get-SessionAccount.ps1` | Reports which Claude account the current session is actually logged into by comparing `~/.claude.json`'s CLI login against a `CLAUDE_USER_DATA_DIR` desktop profile's `lastKnownAccountUuid`, recovering the desktop account's email from profile storage when the two accounts differ |

## Subdirectories

| Entry | Description |
|---|---|
| `dev_env_scripts_constants/` | Named constants (`timing.py`) for scripts in this directory |
| `sync_to_cursor/` | Package that builds Cursor `.mdc` files from Claude rules and docs |
| `tests/` | pytest suite for the Python scripts and Pester (`*.Tests.ps1`) suite for the PowerShell scripts in this directory |

## Running tests

Python scripts (pytest):

```bash
python -m pytest packages/claude-dev-env/scripts/tests/
```

PowerShell scripts (Pester 5+, `*.Tests.ps1`):

```powershell
Invoke-Pester -Path packages/claude-dev-env/scripts/tests/
```
