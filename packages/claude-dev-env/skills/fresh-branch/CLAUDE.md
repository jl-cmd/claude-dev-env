# fresh-branch

Creates a new branch from fresh-fetched `origin/main` inside an isolated worktree under `Temp/<agent>/<branch-name>`. Does not push, open a PR, or run `checkout -b` in the caller tree.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Phases, checklist, execute-vs-read for the CLI, gotchas |
| `scripts/create_fresh_branch.py` | Deterministic CLI: fetch base, `git worktree add -b`, JSON stdout |
| `scripts/fresh_branch_git_commands.py` | Git command helpers: fetch, ref checks, `git worktree add -b --no-track` |
| `scripts/test_create_fresh_branch.py` | Behavioral tests with temporary git repos |
| `scripts/test_fresh_branch_git_commands.py` | Behavioral tests for the git command helpers |
| `scripts/fresh_branch_scripts_constants/` | Constants package (`fresh_branch_cli_constants`) for the CLI |
