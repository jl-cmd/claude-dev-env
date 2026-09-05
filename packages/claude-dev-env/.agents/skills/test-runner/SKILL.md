---
name: test-runner
description: >-
  Run pytest or Playwright through the repository's explicit test command.
  Performs the Django and Playwright readiness checks before launching the
  selected child process. Use when running tests in a repository with local
  Django or frontend services.
---

# test-runner

Run tests through the bundled command so setup checks and the test process are
one visible operation. The command accepts one supported runner after `--` and
passes its arguments to that runner without a shell.

## Command

Run from the repository that owns the tests:

```text
python "${CLAUDE_SKILL_DIR}/scripts/run_tests.py" -- python -m pytest <pytest-arguments>
python "${CLAUDE_SKILL_DIR}/scripts/run_tests.py" -- npx playwright test <playwright-arguments>
```

Use `--project <path>` when the test repository is not the current directory:

```text
python "${CLAUDE_SKILL_DIR}/scripts/run_tests.py" --project "<repository>" -- python -m pytest <pytest-arguments>
```

The supported runner forms are `pytest`, `python -m pytest`, `playwright test`,
and `npx playwright test`. The child receives the exact arguments after `--`,
inherits the current environment, writes directly to the current output
streams, runs with the selected project as its working directory, and returns
its exit status.

## Preflight

The command returns nonzero and launches no child when a required check fails.

- A pytest run in a project without `manage.py` runs without preflight.
- A pytest run in a Django project requires `db.sqlite3` and a healthy Django
  server. The URL defaults to `http://localhost:8000` and uses an explicit URL
  present in the child arguments when one is supplied.
- A Playwright run checks its target server, validates a detected Django
  `runserver` process uses `--test-db`, rejects conflicting Django servers from
  different worktrees, and uses the URL default `http://localhost:3000`.
- When the project contains `frontend/`, the command runs `npm run build` in
  that directory, then `python manage.py collectstatic --noinput` in the
  project directory before Playwright starts.

The command does not parse shell syntax. Keep pipes, redirects, `cd`, and
background operators outside this command. Run this command directly so its
exit status reaches the caller.

## Refusals

Use the normal runner for unsupported commands. This command only accepts the
four runner forms listed above and does not install dependencies, start a
server, run migrations, or repair a failed preflight.

## Files

- `SKILL.md` — invocation, checks, and command boundary.
- `scripts/run_tests.py` — preflight and child-process command.
- `scripts/test_run_tests.py` — focused command and preflight tests.
- `scripts/test_runner_constants/` — shared command names, messages, and limits.
