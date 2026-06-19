# bugteam/reference

Expanded workflow detail for the `bugteam` skill. Load a file from this directory when the orchestration stub in `SKILL.md` is not enough — for example, when debugging GitHub review shape, understanding gate semantics, or working through teardown edge cases.

## Key files

| File | Purpose |
|---|---|
| `README.md` | Index of all files in this directory with one-line domain summaries. |
| `team-setup.md` | Permissions grant, PR scope resolution, run name, temp dir, and loop state. |
| `audit-and-teammates.md` | Pre-audit CODE_RULES gate, full cycle numbering, AUDIT and FIX action detail. |
| `audit-contract.md` | Finding shape (Shape A / B), Haiku secondary merge rules, post-fix self-audit. |
| `github-pr-reviews.md` | Per-loop review posting, `jq`+`gh api` payloads, inline anchors, fallbacks, REST endpoints. |
| `teardown-publish-permissions.md` | Teardown steps, PR description rewrite via `pr-description-writer`, permission revoke, final report. |
| `design-rationale.md` | Why clean-room subagents, when `/bugteam` applies, refusal reasons. |
| `copilot-gap-analysis.md` | Historical gap analysis (reference only). |

## Subdirectories

| Directory | Role |
|---|---|
| `obstacles/` | Per-step obstacle guides — one file per common failure point (e.g., write XML, resolve thread, push, test suite). |
