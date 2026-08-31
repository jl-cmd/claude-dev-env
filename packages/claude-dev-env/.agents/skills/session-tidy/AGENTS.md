# session-tidy

Audits, cleans, and consolidates session logs in the Obsidian vault — fixes format drift, resolves orphaned next-steps, updates stale statuses, and generates project rollup summaries.

**Trigger:** `/session-tidy`, "tidy sessions", "clean up session logs", "session audit".

## Purpose

Maintenance utility for the `sessions/[Project]/` vault directories. Enforces the session-log format contract, moves uncategorized files into project subfolders, and generates `Summary.md` rollup files for projects with 3+ sessions.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | The complete skill — four phases (preflight, audit, propose changes, execute + verify). No companion files. |

## Format contract enforced

- **Path:** `sessions/[Project]/[N]. [Title].md`
- **Frontmatter:** `type`, `project`, `session`, `date`, `status`, `blocked`, `tags` — all needed.
- **Status rules:** `completed` + `blocked: true` is contradictory; `in-progress` or `blocked` older than 7 days is stale.
- **Content:** outcome-oriented `###` headers with one emoji; no play-by-play narration.

## Four phases

1. **Preflight** — resolve backend (headless vault, Obsidian MCP, or local vault).
2. **Audit** — check each file for naming, frontmatter completeness, status coherence, orphaned next-steps, and categorization.
3. **Propose changes** — report findings; wait for user approval before changing anything.
4. **Execute + verify** — rename files, fix frontmatter, update statuses, clean orphaned next-steps, generate `Summary.md` rollups.

## Conventions

- `disable-model-invocation: true` is set.
- Changes need explicit user approval from Phase 2's report — the skill never auto-applies without approval.
- Companion to `/session-log` (creates sessions) and `/recall` (reads vault).
- `/session-tidy` targets Markdown session format; HTML sessions from `/session-log` may be mis-audited or get incorrect rename proposals.
