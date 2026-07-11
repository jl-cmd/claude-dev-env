# _shared

Support code shared across multiple skills. Each subdirectory targets a specific cross-skill concern.

## Subdirectories

| Directory | Role |
|---|---|
| `pr-loop/` | Prompt templates and Python helper scripts used by both `bugteam` and `pr-converge` for their audit-fix loop. |

Files here are not skills themselves and have no `SKILL.md`. They install alongside each consuming skill via the install pipeline in `packages/claude-dev-env/bin/install.mjs`.
