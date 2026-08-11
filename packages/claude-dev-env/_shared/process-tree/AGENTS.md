# _shared/process-tree

One home for ending a spawned process together with every descendant it
started. Callers that capture a CLI's output import it so a grandchild can
never outlive the run and hold the capture pipe open.

## Consumers

| Caller | Use |
|---|---|
| `scripts/grok_headless_runner.py` | Kills a timed-out worker's tree between drain attempts |
| `skills/codex-review/scripts/run_codex_review.py` | Kills the review tree on timeout, then drains |
| `skills/codex-review/scripts/codex_usage_probe.py` | Tears the app-server tree down after the rate-limits exchange |

A skill script reaches this home the way the bugteam scripts reach
`_shared/pr-loop/scripts`: it puts the directory on `sys.path` and imports by
module name. `bin/install.mjs` copies `_shared` and `scripts` together, and
every install group that carries a consumer carries `_shared`, so the import
resolves in the repository and under `~/.claude` alike.

## Key files

| File | Purpose |
|---|---|
| `scripts/process_tree_kill.py` | `terminate_process_tree` (poll, platform tree kill, re-poll, `Popen.kill()` fallback), `kill_process_tree_by_identifier`, and `should_start_new_session` for the matching `Popen` flag |
| `scripts/test_process_tree_kill.py` | Behavioral tests for every public entry point here, each platform branch, each failure the helper swallows, and the `Popen.kill()` fallback |
| `scripts/config/process_tree_scripts_constants/process_tree_kill_constants.py` | The taskkill command, its `/T`, `/F`, and `/PID` flags, and the bound on the kill command |
| `scripts/pyproject.toml` | mypy configuration; `check.ps1` runs it under the `mypy-process-tree` label |

## Platform guard

Both the branch selector and the POSIX helper compare `sys.platform` against
the literal `"win32"`. That literal is what mypy narrows on: behind a named
constant, `os.getpgid`, `os.killpg`, and `signal.SIGKILL` fail type checking on
Windows.

## Pairing rule

`os.killpg` signals a whole process group, so a child sharing the caller's
group takes the caller down with it. Every `Popen` whose tree this module ends
passes `start_new_session=should_start_new_session()`.
