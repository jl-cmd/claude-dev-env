# .cursor/skills/parallel-debug

The `parallel-debug` Cursor skill. Drives the pr-converge convergence loop across all open PRs in `jl-cmd/claude-code-config`, paced by an AutoHotkey auto-typer.

## Key files

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill definition — frontmatter trigger (`parallel-debug`), loop goal, one-time AHK setup, PR discovery commands, and the per-tick convergence protocol |

## What this skill does

Activating this skill starts a convergence loop that:

1. Discovers all open PRs via `gh api`.
2. For each PR: runs Cursor BugBot, spawns a bugteam audit, applies fixes, and posts inline review replies.
3. Marks each converged PR ready (`gh pr ready`) when bugbot and bugteam are both clean on the same HEAD.
4. Ends every response with `Awaiting next "continue" tick.` — the AHK pacer types `continue` every 5 minutes to advance the loop.

## Setup

AutoHotkey v2 must be installed at `C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe`. Before the first tick, resolve the Cursor window PID and launch the AHK pacer via the scripts referenced in `SKILL.md`.

## Conventions

- This skill is Cursor-only. The Claude Code equivalent is the `pr-converge` skill in `packages/claude-dev-env/skills/pr-converge/`.
- Do not run this skill from a Claude Code (non-Cursor) session — use the `pr-converge` or `loop` skill there instead.
