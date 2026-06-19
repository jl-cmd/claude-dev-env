# .github/workflows

GitHub Actions workflow definitions. Each YAML file is one workflow.

## Files

| File | Trigger(s) | What it does |
|------|-----------|--------------|
| `pr-check.yml` | PR opened/edited/synchronized/reopened against `main` | Validates the PR title against Conventional Commits using `amannn/action-semantic-pull-request`. Allowed types: `feat fix chore docs style refactor perf test build ci revert`. Blocks merge on failure. |
| `publish.yml` | Push to `main`, schedule (hourly), manual | Runs `release-please-oss/release-please-action` to manage the release PR and `CHANGELOG.md`. When a release is created, publishes the `claude-dev-env` package to npm with provenance (`id-token: write`). |
| `fan-out-ai-rules.yml` | Push to `main` when `AGENTS.md` changes, schedule (Monday noon UTC), manual | Mints GitHub App tokens for `JonEcho` and `jl-cmd` org, then calls `.github/scripts/sync_ai_rules.py` (or `scripts/fan_out_dispatch.py`) to dispatch `repository_dispatch` events to all registered target repos. |
| `sync-ai-rules.yml` | `repository_dispatch` type `sync-ai-rules`, manual | Listener that runs inside a target repo. Checks out the default branch and calls `.github/scripts/sync_ai_rules.py` to write the synced `AGENTS.md` and `.cursor/BUGBOT.md`. Needs `contents: write` and `issues: write` permissions. |
| `ci-sync-ai-rules.yml` | PR changing `sync_ai_rules.py`, `fan_out_dispatch.py`, their tests, or `pytest.ini` | Runs `pytest tests/test_sync_ai_rules.py tests/test_fan_out_dispatch.py` to verify the sync scripts before merge. |

## Conventions

- `publish.yml` is gated on `release-please-manifest.json`; do not bump the version manually.
- `fan-out-ai-rules.yml` requires two GitHub App secrets (`APP_ID`, `APP_PRIVATE_KEY`) to mint tokens for the two GitHub accounts that own target repos.
- `sync-ai-rules.yml` ships to dependent repos as part of the AI rules sync; the copy here is the authoritative template.
- The Python AI-rules workflows (`fan-out-ai-rules.yml`, `sync-ai-rules.yml`, `ci-sync-ai-rules.yml`) use `actions/checkout@v5` and `actions/setup-python@v5` with Python 3.11. `pr-check.yml` uses neither; `publish.yml` uses `actions/checkout@v5` and pins no Python.
