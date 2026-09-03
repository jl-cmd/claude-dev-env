---
name: recovering-codex-startup
description: >-
  Diagnose Windows Codex desktop/CLI startup with fresh read-only process evidence. Triggers: Codex will not start, Codex desktop/CLI stuck, suspended Codex process, stale Codex process, Windows Codex startup.
---

# Recovering Codex startup

## Principle

Collect a fresh, read-only process listing before you say Codex is stuck, stale, or running.
Report only what that listing supports. Do not change process or installation state.

## Gotchas

- A process name alone does not prove that Codex is the affected process.
- Report the executable path, process name, start time, and owner. Mark unavailable fields as unavailable.
- Do not inspect other applications, process trees, or change process state.
- Do not call a process stale or suspended without fresh supporting evidence.
- Route installation issues to `/run-claude-dev-env`.
- Run `/privacy-hygiene` before durable output.

## When this applies

Use this skill only for Windows Codex desktop or CLI startup diagnosis.

For a non-Windows run, return exactly:
`This runbook supports Windows Codex startup recovery only.`

## Process

1. Register the tasks in `reference/task-seeds.md`.
2. Read `../../../rules/verify-runtime-state.md`.
3. Confirm Windows and collect a fresh timestamp.
4. Use read-only Windows tools to inspect Codex processes only.
5. Record process name, executable path, start time, and owner.
6. Separate observation from diagnosis and state when no match exists.
7. Route installation evidence to `/run-claude-dev-env`.
8. Run `/privacy-hygiene` before saving or publishing a report.

Do not change process or installation state. A human must authorize any later
process or installation change.

## Sub-skills

| Skill | Use | Produces |
| --- | --- | --- |
| `/run-claude-dev-env` | Installation evidence | Installation diagnosis |
| `/privacy-hygiene` | Before durable output | Privacy-reviewed output |

## Files

- `SKILL.md`. Diagnosis rules and process.
- `reference/task-seeds.md`. Ordered tasks for one diagnosis.

```text
recovering-codex-startup/
├── SKILL.md
└── reference/
    └── task-seeds.md
```
