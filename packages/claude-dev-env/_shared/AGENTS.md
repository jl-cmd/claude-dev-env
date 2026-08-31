# _shared

Cross-cutting runtime assets shared by multiple skills. The PR-loop skills (`bugteam`, `pr-converge`, `findbugs`, `fixbugs`) are one such cluster; other clusters live here too. Files here are installed into `~/.claude/_shared/` by `bin/install.mjs` alongside the skill directories that import them.

Shared assets use `~/.claude/rules/asd-ste100-language.md` for user-facing word choice, sentence style, tone, punctuation, and prose form. Each asset keeps its workflow-specific structure.

## Contents

| Entry | Description |
|---|---|
| `pr-loop/` | Docs, scripts, and constants for the PR-loop workflow suite |
| `advisor/` | Warm-advisor spawn-and-consult protocol for `team-advisor` and `orchestrator` |
| `process-tree/` | One process-tree kill helper for every script that captures a spawned CLI's output |

## Install path

`bin/install.mjs` copies this entire directory tree verbatim to `~/.claude/_shared/`. Skills reference files here by relative path from their own skill root (e.g. `../../_shared/pr-loop/audit-contract.md`).
