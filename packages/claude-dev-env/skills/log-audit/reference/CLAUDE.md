# log-audit/reference

Reference material for the `log-audit` skill.

## Key files

| File | Purpose |
|---|---|
| `charter.md` | The agent's contract: what it watches (this repo's hook-block log and diagnostic extractor pipeline), what it looks for (recurring errors and timing regressions), what it files per finding (grouped draft fix PR or tracked optimization issue), how it mines reviewer defect patterns into skill-definition proposals, and the per-cycle report it emits. Cycle state lives under `~/.claude/runtime/log-audit/`; the agent runs on a sub-hour cadence. |
