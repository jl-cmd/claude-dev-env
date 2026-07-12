# .github/workflows

GitHub Actions workflow definitions. Each YAML file is one workflow.

## Files

| File | Trigger(s) | What it does |
|------|-----------|--------------|
| `ci-tests.yml` | Push to `main`, PR against `main` | Runs the full Python suite (root `tests/` + `packages/claude-dev-env`, Python 3.12, deselect lists under `.github/ci/`) and the JS suite (`npm test` in `packages/claude-dev-env`, Node 24). `permissions.contents: read` only. |
| `pr-check.yml` | PR opened/edited/synchronized/reopened against `main` | Validates the PR title against Conventional Commits using `amannn/action-semantic-pull-request`. Allowed types: `feat fix chore docs style refactor perf test build ci revert`. Blocks merge on failure. |
| `publish.yml` | Push to `main`, schedule (hourly), manual | Runs `release-please-oss/release-please-action` to manage the release PR and `CHANGELOG.md`. When a release is created, publishes the `claude-dev-env` package to npm with provenance (`id-token: write`). |
| `fan-out-ai-rules.yml` | Push to `main` when `AGENTS.md` changes, schedule (Monday noon UTC), manual | Mints GitHub App tokens for the two configured owner scopes (repo variables `FANOUT_OWNER_1` and `FANOUT_OWNER_2`), then calls `.github/scripts/sync_ai_rules.py` (or `scripts/fan_out_dispatch.py`) to dispatch `repository_dispatch` events to all registered target repos. |
| `sync-ai-rules.yml` | `repository_dispatch` type `sync-ai-rules`, manual | Listener that runs inside a target repo. Checks out the default branch and calls `.github/scripts/sync_ai_rules.py` to write the synced `AGENTS.md` and `.cursor/BUGBOT.md`. Needs `contents: write` and `issues: write` permissions. |

## Conventions

- `publish.yml` is gated on `release-please-manifest.json`; do not bump the version manually.
- `fan-out-ai-rules.yml` requires two GitHub App secrets (`APP_ID`, `APP_PRIVATE_KEY`) to mint tokens for the two GitHub accounts that own target repos.
- `sync-ai-rules.yml` ships to dependent repos as part of the AI rules sync; the copy here is the authoritative template.
- `ci-tests.yml` uses `actions/checkout@v5`, `actions/setup-python@v5` (Python 3.12), and `actions/setup-node@v4` (Node 24). Deselect node IDs live in `.github/ci/live-post-audit-deselects.txt` and `.github/ci/windows-semantics-node-ids.txt`. The root suite covers the sync-ai-rules modules on every PR, so there is no separate path-filter workflow for those two test files.
- The Python AI-rules workflows (`fan-out-ai-rules.yml`, `sync-ai-rules.yml`) use `actions/checkout@v5` and `actions/setup-python@v5` with Python 3.11. `pr-check.yml` uses neither; `publish.yml` uses `actions/checkout@v5` and pins no Python.
