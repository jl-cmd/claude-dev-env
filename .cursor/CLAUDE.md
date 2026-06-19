# .cursor

Cursor IDE configuration for this repo. This directory has the auto-generated BugBot rules file and a `skills/` directory for Cursor-specific skills.

## Key files

| File | Purpose |
|------|---------|
| `BUGBOT.md` | Auto-generated AI review rules for Cursor BugBot. **Do not hand-edit.** The source of truth is `AGENTS.md` at the repo root; `.github/workflows/sync-ai-rules.yml` and `sync_ai_rules.py` regenerate this file and prepend a sync header on every `AGENTS.md` push to `main`. |

## Subdirectories

| Directory | Role |
|-----------|------|
| `skills/` | Cursor-specific skills that run inside Cursor sessions |

## Conventions

- Edit `AGENTS.md` at the repo root to change review rules. Do not edit `BUGBOT.md` directly — the sync workflow overwrites it.
- `BUGBOT.md` carries a `<!-- SYNC-HEADER-START -->` / `<!-- SYNC-HEADER-END -->` block at the top that records the source commit and sync timestamp; the workflow updates this block on each run.
- The `.cursorignore` file at the repo root controls which files Cursor indexes.
