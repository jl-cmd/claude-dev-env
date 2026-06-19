# pr-loop

Shared infrastructure for the PR audit-fix loop used by `bugteam` and `pr-converge`. Provides the XML prompt template, Python runtime scripts, and named constants that both skills invoke during each loop tick.

## Subdirectories

| Directory | Role |
|---|---|
| `prompts/` | XML agent prompt templates. |
| `scripts/` | Python scripts for loop state management, prompt building, outcome recording, path resolution, and preflight checks. |

## Key files

| File | Role |
|---|---|
| `prompts/pr-consistency-audit.xml` | Structured prompt artifact for the cross-file consistency audit agent. |
| `packages/claude-dev-env/skills/_shared/pr-loop/scripts/build_audit_prompt.py` | Assembles the audit agent prompt from loop state and the constants module. |
| `packages/claude-dev-env/skills/_shared/pr-loop/scripts/build_fix_prompt.py` | Assembles the fix agent prompt from loop state and findings. |
| `packages/claude-dev-env/skills/_shared/pr-loop/scripts/init_loop_state.py` | Initializes the per-PR loop state JSON file. |
| `packages/claude-dev-env/skills/_shared/pr-loop/scripts/write_audit_outcomes.py` | Writes the per-loop audit outcome XML into the workspace. |
| `packages/claude-dev-env/skills/_shared/pr-loop/scripts/write_fix_outcomes.py` | Writes the per-loop fix outcome XML into the workspace. |
| `packages/claude-dev-env/skills/_shared/pr-loop/scripts/preflight_worktree.py` | Verifies the working directory is a healthy worktree for the target PR's repo. |
| `packages/claude-dev-env/skills/_shared/pr-loop/scripts/teardown_worktrees.py` | Removes loop worktrees on clean exit. |
| `packages/claude-dev-env/skills/_shared/pr-loop/scripts/_path_resolver.py` | Resolves workspace and worktree paths from PR metadata. |
| `packages/claude-dev-env/skills/_shared/pr-loop/scripts/_cli_utils.py` | Shared CLI argument parsing helpers. |
| `packages/claude-dev-env/skills/_shared/pr-loop/scripts/_xml_utils.py` | XML serialization helpers. |
| `scripts/skills_pr_loop_constants/` | Named constants package imported by the scripts above. |
