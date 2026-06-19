# _shared

Cross-cutting runtime assets shared by multiple PR-loop skills (`bugteam`, `pr-converge`, `findbugs`, `fixbugs`). Files here are installed into `~/.claude/_shared/` by `bin/install.mjs` alongside the skill directories that import them.

## Contents

| Entry | Description |
|---|---|
| `pr-loop/` | Docs, scripts, and constants for the PR-loop workflow suite |

## Install path

`bin/install.mjs` copies this entire directory tree verbatim to `~/.claude/_shared/`. Skills reference files here by relative path from their own skill root (e.g. `../../_shared/pr-loop/audit-contract.md`).
