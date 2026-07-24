# _shared

Cross-cutting runtime assets shared by multiple skills. Clusters live under this directory (PR-loop skills, advisor protocol, and others). Files install into ~/.claude/skills/_shared/ via the skills tree in bin/install.mjs.

## Contents

| Entry | Description |
|---|---|
| pr-loop/ | Docs, scripts, constants, prompts, and the portable driver for the PR-loop workflow suite |
| advisor/ | Warm-advisor spawn-and-consult protocol for team-advisor and orchestrator |

## Install path

bin/install.mjs copies this tree as part of skills/_shared/ to ~/.claude/skills/_shared/. Skills reference files here by relative path from their own skill root (for example ../_shared/pr-loop/audit-contract.md).
