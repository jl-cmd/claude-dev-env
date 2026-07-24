# grok-spawn

**Trigger:** `/grok-spawn`, "spawn grok workers", "grok worker fleet", "run this with grok workers", "headless grok batch".

Orchestrator playbook for fleets of headless grok CLI workers. Names the runtime
scripts and the order to call them; all spawn logic lives in those scripts. The
calling session verifies results and owns every commit, push, and GitHub post.

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Tool-profile choices the hub cites on demand. |

## Key files

| File | Role |
|---|---|
| `SKILL.md` | Entry protocol: when to use, worker environment, constraints, preflight → scaffold → fill → launch → collect → verify. |
| `reference/flag-profiles.md` | Readonly vs build profile meaning, `is_repo_only`, the `--agent` charter binding, and the profile cheat sheet. |

## Entry point

All runtime scripts live in `$HOME/.claude/scripts/`
(`grok_worker_preflight.py`, `grok_batch_scaffold.py`, `spawn_grok_batch.py`,
`grok_headless_runner.py`) after install. `grok_batch_scaffold.py` writes the
worker part files and the wired batch-spec skeleton; the session fills the
task-specific content, then launches with `spawn_grok_batch.py`. Constants live
in `scripts/dev_env_scripts_constants/`.
