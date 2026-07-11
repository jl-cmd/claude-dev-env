# auditing-claude-config

**Trigger:** `/auditing-claude-config`, reviewing the startup instruction load, `/memory` showing unexpected files, adding new rules, periodic config hygiene.

Audits a Claude Code setup — user `CLAUDE.md`, `~/.claude/rules/`, project `.claude/` — for context-budget waste: duplicate `@`-imports, always-on rules that could be path-scoped or turned into skills, and oversized files. Produces a migration table with line savings.

## Key files

| File | Role |
|---|---|
| `SKILL.md` | Full audit protocol: inventory the always-loaded set, find duplicate imports, classify each rule, produce the migration table, stage recommendations by risk, and verify lazy-load behavior with an optional probe hook. |

## What the skill produces

1. **Baseline** — total always-loaded lines, broken down by file.
2. **Migration table** — one row per rule: current lines, verdict, specific action, lines removed from preload.
3. **Recommended next step** — the single highest-leverage change.
4. **Open questions** — anything not verified by the probe hook.

No scripts or workflow files. The skill body holds all logic.
