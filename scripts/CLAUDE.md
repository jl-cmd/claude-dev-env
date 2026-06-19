# scripts/

Repo-level Python scripts and shell utilities for the AI rules fan-out system.

## Purpose

Holds scripts that run as part of GitHub Actions workflows or as CLI tools for
operating the AI rules sync fleet. These are distinct from the hook scripts in
`packages/claude-dev-env/hooks/`, which ship to users; everything here is repo
infrastructure.

## Files

| File | Role |
|------|------|
| `fan_out_dispatch.py` | Dispatcher for the AI rules fan-out sync. Enumerates target repos under `JonEcho` and `jl-cmd`, checks opt-out sentinels, fires `repository_dispatch` events, then polls each listener for its conclusion. Run by `.github/workflows/fan-out-ai-rules.yml`. Reads `JONECHO_TOKEN` and `JLCMD_TOKEN` from the environment. |
| `bootstrap-listeners.sh` | Idempotent shell script that copies `sync-ai-rules.yml` and `sync_ai_rules.py` into target repos and opens bootstrap PRs. Run from a machine with `gh` auth before onboarding a new repo. |

## Running the dispatcher locally

```bash
JONECHO_TOKEN=<token> JLCMD_TOKEN=<token> python scripts/fan_out_dispatch.py
```

## Tests

Unit tests for `fan_out_dispatch.py` live at `tests/test_fan_out_dispatch.py`.
Run with:

```bash
python -m pytest tests/test_fan_out_dispatch.py
```

## Conventions

- Keep all constants in `UPPER_SNAKE_CASE` at module scope inside the script; never inline magic values in function bodies.
- HTTP calls go through `make_github_api_request` — do not open `urllib.request` connections elsewhere in the module.
- Scripts here do not import from `packages/claude-dev-env/`; they may import from `config/`.
