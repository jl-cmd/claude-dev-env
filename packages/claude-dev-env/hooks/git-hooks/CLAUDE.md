# hooks/git-hooks

Native git hooks that run outside the Claude Code lifecycle — invoked directly by git at commit and push time. The installer copies these scripts into the user's shared git-hooks directory (`core.hooksPath`).

## Key files

| File | Git hook | What it does |
|---|---|---|
| `pre_commit.py` | `pre-commit` | Runs the CODE_RULES gate (`precommit_code_rules_gate.py`) over staged changes; exits 1 when any staged file has a blocking violation |
| `pre_push.py` | `pre-push` | Blocks a push that would land a non-`main` local branch onto remote `main` (or `master`), then runs the CODE_RULES gate over the commits about to be pushed |
| `post_commit.py` | `post-commit` | Runs after a commit lands; performs any post-commit bookkeeping |
| `gate_utils.py` | — | Shared helpers: resolves the gate script path, checks that the path is a safe regular file |
| `test_config.py` | — | Test configuration helpers |
| `test_gate_utils.py` | — | Tests for `gate_utils.py` |
| `test_pre_commit.py` | — | Tests for `pre_commit.py` |
| `test_pre_push.py` | — | Tests for `pre_push.py` |

## Subdirectory

| Directory | Role |
|---|---|
| `git_hooks_constants/` | Shared constants imported by the git-hook scripts |

## Conventions

- The installer strips the `_` and `.py` suffix when copying into the live git-hooks path (e.g. `pre_commit.py` becomes `pre-commit`).
- Constants (exit codes, argument names, error messages) live in `git_hooks_constants/` and are imported at the top of each script.
- Run tests with `python -m pytest git-hooks/test_<name>.py`.
