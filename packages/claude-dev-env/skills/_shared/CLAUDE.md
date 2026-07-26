# _shared

Cross-cutting runtime assets shared by multiple skills. Each subdirectory targets a specific cross-skill concern. The PR-loop skills (`bugteam`, `pr-converge`, `autoconverge`, `findbugs`, `fixbugs`) are one such cluster; other clusters live here too.

## Subdirectories

| Directory | Role |
|---|---|
| `pr-loop/` | Docs, prompt templates, Python helper scripts, and constants for the PR-loop workflow suite, used by `bugteam`, `pr-converge`, and `autoconverge` for their audit-fix loop. |
| `advisor/` | Warm-advisor spawn-and-consult protocol for `team-advisor` and `orchestrator`. |

Files here are not skills themselves and have no `SKILL.md`.

## Install path

`bin/install.mjs` copies this directory tree alongside its consuming skills under `~/.claude/skills/_shared/`. Skills reference files here by relative path from their own skill root (for example `../_shared/pr-loop/audit-contract.md`).
