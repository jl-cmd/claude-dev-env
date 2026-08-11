# grok-spawn

**Trigger:** `/grok-spawn`, "spawn grok workers", "grok worker fleet", "run this with grok workers", "headless grok batch".

Orchestrator playbook for fleets of headless grok CLI workers. Composes
`grok_worker_preflight.py` and `spawn_grok_batch.py` by name. Holds no spawn
logic of its own. The calling session verifies results and owns every commit,
push, and GitHub post.

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Prompt-part templates and tool-profile flag docs the hub cites on demand. |

## Key files

| File | Role |
|---|---|
| `SKILL.md` | Entry protocol: when to use, gotchas, preflight → batch spec → launch → collect → verify. |
| `reference/worker-briefs.md` | Readonly investigation brief, build brief (edits and tests only), report contract. |
| `reference/flag-profiles.md` | Readonly vs build flag sets, shared flags, leader-socket and stagger rules, `--agent` note. |

## Entry point

No skill-local scripts. Runtime lives in `$HOME/.claude/scripts/`
(`grok_worker_preflight.py`, `spawn_grok_batch.py`, `grok_headless_runner.py`)
after install. Constants live in `scripts/dev_env_scripts_constants/`.
