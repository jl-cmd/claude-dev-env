# .github/workflows

GitHub Actions workflow definitions. Each YAML file is one workflow.

## Files

| File | Trigger(s) | What it does |
|------|-----------|--------------|
| `ci-tests.yml` | Push to `main`, PR against `main` | Cheap `changes` job (`dorny/paths-filter`) sets `package_suite`, `root_suite`, and `javascript` outputs. On PRs, the package suite (`packages/claude-dev-env`), the root suite (`tests/`), and the JS suite (`npm test` in `packages/claude-dev-env`, Node 24) each run only when their filter matches; push to `main` always runs all three. Both Python suites run on Python 3.12 and build their `--deselect` set from the lists under `.github/ci/`. The quality-gate job (`check.ps1 -SkipTests` under pwsh: ruff + mypy) and the windows-semantics micro-suite on `windows-latest` (the seven node IDs from `.github/ci/windows-semantics-node-ids.txt`) both gate on `needs: changes` and the `package_suite` filter; the enforcer pytest suite runs inside the package-suite job. Permissions: `contents: read` and `pull-requests: read` (paths-filter on PRs). |
| `pr-check.yml` | PR opened/edited/synchronized/reopened against `main` | Validates the PR title against Conventional Commits using `amannn/action-semantic-pull-request`. Allowed types: `feat fix chore docs style refactor perf test build ci revert`. Blocks merge on failure. |
| `publish.yml` | Push to `main`, schedule (hourly), manual | Runs `release-please-oss/release-please-action` to manage the release PR and `CHANGELOG.md`. When a release is created, publishes the `claude-dev-env` package to npm with provenance (`id-token: write`). |
| `fan-out-ai-rules.yml` | Push to `main` when `AGENTS.md` changes, schedule (Monday noon UTC), manual | Mints GitHub App tokens for the two configured owner scopes (repo variables `FANOUT_OWNER_1` and `FANOUT_OWNER_2`), then calls `.github/scripts/sync_ai_rules.py` (or `scripts/fan_out_dispatch.py`) to dispatch `repository_dispatch` events to all registered target repos. |
| `sync-ai-rules.yml` | `repository_dispatch` type `sync-ai-rules`, manual | Listener that runs inside a target repo. Checks out the default branch and calls `.github/scripts/sync_ai_rules.py` to write the synced `AGENTS.md` and `.cursor/BUGBOT.md`. Needs `contents: write` and `issues: write` permissions. |

## Conventions

- `publish.yml` is gated on `release-please-manifest.json`; do not bump the version manually.
- `fan-out-ai-rules.yml` requires two GitHub App secrets (`APP_ID`, `APP_PRIVATE_KEY`) to mint tokens for the two GitHub accounts that own target repos.
- `sync-ai-rules.yml` ships to dependent repos as part of the AI rules sync; the copy here is the authoritative template.
- `ci-tests.yml` uses `actions/checkout@v5`, `dorny/paths-filter` (SHA-pinned), `actions/setup-python@v5` (Python 3.12), and `actions/setup-node@v4` (Node 24). Path filters skip inert PR paths; push to `main` always runs full suites. Every filter includes all of `packages/claude-dev-env/**` (package markdown is fixture-bearing); the `root_suite` filter adds `docs/**`, `scripts/**`, `.github/workflows/**`, and `.cursor/BUGBOT.md` on top of the `package_suite` set. Deselect node IDs live in `.github/ci/live-post-audit-deselects.txt`, `.github/ci/windows-semantics-node-ids.txt`, `.github/ci/known-pending-deselects.txt`, and `.github/ci/author-swap-deselects.txt`; both Python suites build the `--deselect` set by sourcing `.github/ci/build-deselect-args.sh`. The why for each family is the local-only register in `tests/CLAUDE.md`. The root suite covers the sync-ai-rules modules whenever the `root_suite` filter matches, so there is no separate path-filter workflow for those two test files. The quality-gate job runs `check.ps1 -SkipTests` (ruff + mypy); the enforcer pytest suite runs in the package-suite job. The windows-semantics job reads only `windows-semantics-node-ids.txt` and passes those node IDs as a positional select list.
- The Python AI-rules workflows (`fan-out-ai-rules.yml`, `sync-ai-rules.yml`) use `actions/checkout@v5` and `actions/setup-python@v5` with Python 3.11. `pr-check.yml` uses neither; `publish.yml` uses `actions/checkout@v5` and pins no Python.
