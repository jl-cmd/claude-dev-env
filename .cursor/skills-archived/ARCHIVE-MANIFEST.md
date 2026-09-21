# Archived Cursor skills

These skills are archived outside the active Cursor skill tree. Restore one
with the `git mv` command in its row, then restore whatever its workflow needs.

| Directory | Reason | Restore |
|---|---|---|
| `parallel-debug/` | The skill drives the `pr-converge` loop, and `pr-converge` is archived under `packages/claude-dev-env/.agents/skills-archived/`. The installer copies `.agents/skills` alone and prunes a retired name from an existing install, so every `$HOME\.claude\skills\pr-converge\scripts\` path the skill runs is absent. Its Fix Protocol also spawned `clean-coder`, archived by #1404. | `git mv .cursor/skills-archived/parallel-debug .cursor/skills/` after restoring `pr-converge` and `clean-coder` from their own archives. |
