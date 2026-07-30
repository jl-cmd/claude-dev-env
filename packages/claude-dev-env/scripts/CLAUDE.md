# scripts

Utility scripts installed into `~/.claude/scripts/` by `bin/install.mjs`. Each script is a standalone tool a user or hook can invoke directly.

## Scripts

| File | Purpose |
|---|---|
| `claude_chain_runner.py` | Runs a `claude` invocation through a fallback chain (`~/.claude/claude-chain.json`) with `--routing-mode usage_ranked` (default: probe weekly remaining once via `claude_chain_usage` / the usage-pause OAuth probe, highest remaining first) or `ordered_account` (config list order; non-usage failures stop as `advisor_blocked`); falls over only on a usage-limit failure; returns `terminal_status` / optional `session_id` on the outcome; usable as an imported module (`run_claude`) or a CLI. Copy `claude-chain.example.json` to `~/.claude/claude-chain.json` and list your account binaries. Optional per-entry `credentials_path` names that account's OAuth credentials file for the usage probe |
| `claude_chain_usage.py` | Reports remaining weekly usage for every account in `~/.claude/claude-chain.json` via the usage-pause OAuth probe; prints JSON (`accounts` with `weekly_remaining_percent` or null plus `error`); importable `report_chain_weekly_usage` and `rank_accounts_by_weekly_remaining` (highest remaining first, ties keep config order, unmeasurable last). The chain runner consumes this ranking for try order |
| `gh_artifact_upload.py` | Uploads a file to a repo's durable `artifacts` prerelease under a timestamped asset name and prints the permanent download URL a GitHub post can link |
| `grok_headless_runner.py` | Runs one worker as headless `grok`: builds argv with no turn cap (the timeout is the only bound), mints a unique leader socket, captures streams, refuses a timeout that is missing, below `MIN_WORKER_TIMEOUT_SECONDS`, or above the `MAXIMUM_WORKER_TIMEOUT_SECONDS` (5400) ceiling, kills the whole process tree on timeout with grace and retries the kill-and-drain round once, classifies ok/usage_limit/auth_failure/timeout/kill_failed/error; exports `require_timeout_within_bounds` so a dispatcher can apply the same bounds without launching; imported by `spawn_grok_batch.py` and `resolve_worker_spawn.py` |
| `grok_worker_preflight.py` | Soft gate for the headless grok tier: binary on PATH, `grok models` auth, install manifest + role agents, opt-in cached live ping; non-zero exit is fallthrough, not failure |
| `setup_project_paths.py` | One-time bootstrap: discovers git repos via `es.exe` (Everything) and writes `~/.claude/project-paths.json`; never hardcodes scan roots |
| `spawn_grok_batch.py` | Launches a fleet of headless grok workers from a JSON batch spec: gates once through the preflight, refuses a spec whose `timeout_seconds` exceeds `MAXIMUM_WORKER_TIMEOUT_SECONDS` (5400) rather than clamping it, assembles each prompt from part files, optionally binds a unique worker advisor per role via the lead-supplied `advisor.launcher` (placeholder default in constants), injects `advisor_session_id`, requires the same session ENDORSE or bounded CORRECTION/PLAN then ENDORSE, classifies bind/verdict/timeout/missing-launcher failures as `advisor_blocked`, staggers starts, runs each through `grok_headless_runner.py`, and emits one batch summary JSON |
| `sweep_empty_dirs.py` | Deletes empty directories older than a configurable age under a given root; runs once (`--once`) or in continuous-watch mode |
| `sync_to_cursor.py` | Entry point for syncing Claude rules to Cursor `.mdc` files; delegates to the `sync_to_cursor/` package |
| `resolve_worker_spawn.py` | Dispatches a worker role through grok then claude fallback tiers (preflight, headless grok, `claude_agent_required` handoff, optional claude headless); applies `require_timeout_within_bounds` before the preflight, so an out-of-bounds `--timeout-seconds` prints a `timeout_out_of_bounds` outcome and exits 3 on every tier; protocol: [`../_shared/pr-loop/worker-spawn.md`](../_shared/pr-loop/worker-spawn.md) |
| `verify_installable_package.py` | Verifies the published package: runs real `npm pack`, checks every surface in `installable-surfaces.manifest.json` appears in the tarball, requires each `hooks.json` `.py` command to be git-tracked, and smoke-compiles those scripts (`node --check` on `bin/install.mjs`) |

## PowerShell scripts

| File | Purpose |
|---|---|
| `Audit-ShellPolicy.ps1` | Audits Bash tool calls in session transcripts against the `pwsh`-only shell policy |
| `Migrate-ShellPolicy.ps1` | Applies automated fixes for common shell-policy violations found by the audit script |
| `Install-SweepEmptyDirs.ps1` | Registers `sweep_empty_dirs.py` as a scheduled task on Windows |
| `check.ps1` | Runs the full code-quality check suite |
| `Show-Asset.ps1` | Opens files on screen, sizing each image window to the image's pixel dimensions (scaled to fit the screen); non-image files open in their default application |
| `Get-SessionAccount.ps1` | Reports which Claude account the current session is actually logged into by comparing `~/.claude.json`'s CLI login against a `CLAUDE_USER_DATA_DIR` desktop profile's `lastKnownAccountUuid`, recovering the desktop account's email from profile storage when the two accounts differ |
| `Capture-PoolHealth.ps1` | Captures Windows memory pool counters, high-handle processes, and kernel pool tags (via `NtQuerySystemInformation` class 22), prints a threshold verdict with a remediation map, and exits non-zero when any alert threshold fires |

## Subdirectories

| Entry | Description |
|---|---|
| `dev_env_scripts_constants/` | Named constants (`timing.py`, `grok_worker_constants.py`, …) for scripts in this directory, including worker-advisor placeholder launcher/model/effort, four verdict signals, correction cap, and advisor timeout |
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
