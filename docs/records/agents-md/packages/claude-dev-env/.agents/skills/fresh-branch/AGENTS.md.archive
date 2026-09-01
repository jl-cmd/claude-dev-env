# fresh-branch

Creates a new branch from fresh-fetched `origin/main` inside an isolated worktree under a configured root. Default: `<repo-root>/.claude/worktrees/<agent>/<branch-name>`. Optional absolute `--worktree-root` relocates the root (agent and branch still nest under it). Relative roots and path escape fail closed. Does not push, open a PR, or run `checkout -b` in the caller tree.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Phases, checklist, configured-root contract, execute-vs-read for the CLI, gotchas |
| `scripts/create_fresh_branch.py` | Deterministic CLI: resolve configured root (fail closed before fetch), fetch base, `git worktree add -b`, JSON stdout |
| `scripts/fresh_branch_git_commands.py` | Git command helpers: fetch, ref checks, `git worktree add -b --no-track` |
| `scripts/test_create_fresh_branch.py` | Behavioral tests with temporary git repos (default root, explicit root, escape, collisions) |
| `scripts/test_fresh_branch_git_commands.py` | Behavioral tests for the git command helpers |
| `scripts/fresh_branch_scripts_constants/` | Constants package (`fresh_branch_cli_constants`) for CLI flags and error strings |
