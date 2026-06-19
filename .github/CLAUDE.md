# .github

GitHub automation for this repo. Holds issue templates, CI/CD workflows, and the script that syncs AI review rules to dependent repos.

## Subdirectories

| Directory | Role |
|-----------|------|
| `ISSUE_TEMPLATE/` | GitHub issue form templates shown when a user opens a new issue |
| `workflows/` | GitHub Actions workflow files — CI, npm publish, PR title validation, and AI rules sync |
| `scripts/` | Python helper scripts invoked by the workflows |

## Workflows at a glance

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `pr-check.yml` | PR opened/edited against `main` | Validates the PR title matches Conventional Commits format |
| `publish.yml` | Push to `main`, schedule, manual | Runs release-please and publishes the `claude-dev-env` package to npm when a release is created |
| `fan-out-ai-rules.yml` | Push to `main` when `AGENTS.md` changes, schedule (Mon noon UTC), manual | Dispatches `sync-ai-rules` events to all registered dependent repos |
| `sync-ai-rules.yml` | `repository_dispatch` (`sync-ai-rules`), manual | Pulls `AGENTS.md` from this repo and writes it to `.cursor/BUGBOT.md` and `AGENTS.md` in the target repo |
| `ci-sync-ai-rules.yml` | PR touching sync script or its tests | Runs the `sync_ai_rules.py` and `fan_out_dispatch.py` test suites |

## Conventions

- Edit `AGENTS.md` at the repo root to change AI review rules. The fan-out and sync workflows propagate the change to dependent repos automatically.
- The `sync-ai-rules.yml` listener runs in dependent repos, not here; the copy here is the template shipped to them.
- `publish.yml` uses release-please to manage versioning; commit messages must follow Conventional Commits so release-please can compute the next version.
