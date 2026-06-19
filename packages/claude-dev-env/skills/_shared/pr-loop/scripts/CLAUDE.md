# scripts

Python scripts that run the PR audit-fix loop at runtime. Both `bugteam` and `pr-converge` invoke these scripts during each loop tick.

## Key files

| File | Role |
|---|---|
| `build_audit_prompt.py` | Assembles the audit agent prompt from loop state and category constants. |
| `build_fix_prompt.py` | Assembles the fix agent prompt from loop state and findings XML. |
| `init_loop_state.py` | Initializes the per-PR `loop-state.json` file in the workspace directory. |
| `write_audit_outcomes.py` | Writes per-loop audit outcome XML into the workspace. |
| `write_fix_outcomes.py` | Writes per-loop fix outcome XML into the workspace. |
| `preflight_worktree.py` | Verifies the working directory is a healthy git worktree for the target PR's repo. Supports `--mode strict` to abort when the repo does not match. |
| `teardown_worktrees.py` | Removes per-PR worktrees after a clean loop exit. |
| `_path_resolver.py` | Resolves workspace and worktree paths from PR owner, repo, and number. |
| `_cli_utils.py` | Shared CLI argument parsing helpers (argparse wrappers). |
| `_xml_utils.py` | XML serialization helpers for outcome files. |
| `skills_pr_loop_constants/` | Named constants package imported by the scripts above. |

## Tests

Each script has a paired test file (`test_build_audit_prompt.py`, `test_build_fix_prompt.py`, etc.) in this directory. Run with `python -m pytest` from the repo root.
