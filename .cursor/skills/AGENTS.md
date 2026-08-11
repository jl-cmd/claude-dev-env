# .cursor/skills

Cursor-specific skills directory. Each subdirectory is a named skill that a Cursor session can activate.

## Subdirectories

| Directory | Role |
|-----------|------|
| `parallel-debug/` | The `parallel-debug` skill — drives the pr-converge convergence loop across all open PRs in a Cursor session, paced by an AHK auto-typer |

## Conventions

- Each skill directory holds a `SKILL.md` file describing the skill's trigger phrase, setup steps, and tick protocol.
- Skills here are Cursor-session versions of the Claude Code skills in `packages/claude-dev-env/skills/`. They share the same convergence goal but adapt to Cursor's session model (AHK pacing; no `ScheduleWakeup`).
- To add a skill, create a new subdirectory with a `SKILL.md` following the same frontmatter format: `name`, `description`, and the skill body.
