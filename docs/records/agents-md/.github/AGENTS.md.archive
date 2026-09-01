# .github

GitHub automation for this repo. Holds issue templates and CI/CD workflows.

## Subdirectories

| Directory | Role |
|-----------|------|
| `ISSUE_TEMPLATE/` | GitHub issue form templates shown when a user opens a new issue |
| `workflows/` | GitHub Actions workflow files for CI, npm publishing, and PR title validation |
| `ci/` | Pytest deselect node-ID lists for the ubuntu Python suite. Why for each family: local-only register in `tests/CLAUDE.md` |

## Workflows at a glance

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `pr-check.yml` | PR opened/edited against `main` | Validates the PR title matches Conventional Commits format |
| `publish.yml` | Push to `main`, schedule, manual | Runs release-please and publishes the `claude-dev-env` package to npm when a release is created |
| `ci-tests.yml` | Push to `main`, PR against `main` | Runs the full Python suite (root `tests/` + `packages/claude-dev-env`) and the JS suite (`npm test` in `packages/claude-dev-env`) |

## Conventions

- `publish.yml` uses release-please to manage versioning; commit messages must follow Conventional Commits so release-please can compute the next version.
