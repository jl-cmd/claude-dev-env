# .github/workflows

GitHub Actions workflow definitions. Each YAML file is one workflow.

## Files

| File | Trigger(s) | What it does |
|------|-----------|--------------|
| `ci-tests.yml` | Push to `main`, PR against `main` | Cheap `changes` job (`dorny/paths-filter`) sets `package_suite`, `root_suite`, and `javascript` outputs. On PRs, the package suite (`packages/claude-dev-env`), the root suite (`tests/`), and the JS suite (`npm test` in `packages/claude-dev-env`, Node 24) each run only when their filter matches; push to `main` always runs all three. Both Python suites run on Python 3.12 and build their `--deselect` set from the lists under `.github/ci/`. The quality-gate job (`check.ps1 -SkipTests` under pwsh: ruff + mypy) and the windows-semantics micro-suite on `windows-latest` (the eight node IDs from `.github/ci/windows-semantics-node-ids.txt`) both gate on `needs: changes` and the `package_suite` filter; the enforcer pytest suite runs inside the package-suite job. Permissions: `contents: read` and `pull-requests: read` (paths-filter on PRs). |
| `pr-check.yml` | PR opened/edited/synchronized/reopened/ready_for_review against `main` (non-draft only) | Validates the PR title against Conventional Commits using `amannn/action-semantic-pull-request`. Allowed types: `feat fix chore docs style refactor perf test build ci revert`. Blocks merge on failure. |
| `publish.yml` | Push to `main`, schedule (daily, noon UTC), manual | Runs `release-please-oss/release-please-action` to manage the release PR and `CHANGELOG.md`. When a release is created, publishes the `claude-dev-env` package to npm with provenance (`id-token: write`). |

## Conventions

- `publish.yml` is gated on `release-please-manifest.json`; do not bump the version manually.
- `ci-tests.yml` uses `actions/checkout@v5`, `dorny/paths-filter` (SHA-pinned), `actions/setup-python@v5` (Python 3.12), and `actions/setup-node@v4` (Node 24). Path filters skip inert PR paths; push to `main` always runs full suites. Every filter includes all of `packages/claude-dev-env/**` (package markdown is fixture-bearing); the `root_suite` filter adds `docs/**`, `scripts/**`, `.github/workflows/**`, and `.cursor/BUGBOT.md` on top of the `package_suite` set. Deselect node IDs live in `.github/ci/live-post-audit-deselects.txt`, `.github/ci/windows-semantics-node-ids.txt`, `.github/ci/known-pending-deselects.txt`, and `.github/ci/author-swap-deselects.txt`; both Python suites build the `--deselect` set by sourcing `.github/ci/build-deselect-args.sh`. The why for each family is the local-only register in `tests/CLAUDE.md`. The quality-gate job runs `check.ps1 -SkipTests` (ruff + mypy); the enforcer pytest suite runs in the package-suite job. The windows-semantics job reads only `windows-semantics-node-ids.txt` and passes those node IDs as a positional select list.
