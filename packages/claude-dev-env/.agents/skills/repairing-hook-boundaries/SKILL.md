---
name: repairing-hook-boundaries
description: >-
  Repair Claude and Codex hook failures at their first failing boundary. Triggers: Claude/Codex hook failure, blocked hook, hook timeout, invalid hook output, SessionStart, PreToolUse, PostToolUse, UserPromptSubmit, Stop, hooks.json, settings.json, import path, launcher, payload, output envelope, exit status.
---

# Repairing hook boundaries

## Principle

Find the first failing boundary and repair only that boundary. Treat source
registration, installed configuration, launcher and import path, payload,
output envelope, and exit status as separate boundaries.

## Gotchas

- A correct source entry does not prove the installed configuration matches it.
- A valid launcher can receive an invalid payload or emit an invalid envelope.
- State exact source, installed, and repository-root paths for each claim.
- Route installer-only work to `/run-claude-dev-env`.
- Get explicit approval before changing live configuration.
- Run `/privacy-hygiene` before durable output.
- Reuse project validators. Do not copy their commands or implementation here.

## When this applies

Use this skill for Claude or Codex hook failures involving registered events,
settings, launchers, imports, paths, payloads, output envelopes, or exit status.

For installer-only work, say: `Use /run-claude-dev-env for installer work that has no hook-boundary failure.`

## Process

1. Register the tasks in `reference/task-seeds.md`.
2. Record expected and observed behavior. Record exact source, installed, and repository-root paths.
3. Check each boundary in order and identify the first mismatch.
4. Repair only that boundary. Leave unrelated hooks and user settings unchanged.
5. Recheck the boundary and its direct consumer with existing project validators.
6. Use `/run-claude-dev-env` when packaging is involved.
7. Get explicit approval before a live configuration change.
8. Run `/privacy-hygiene` before a durable report or publication.

## Sub-skills

| Skill | Use | Produces |
| --- | --- | --- |
| `/run-claude-dev-env` | Packaging or install work | Install result |
| `/privacy-hygiene` | Durable-output privacy review | Privacy result |

## Files

- `SKILL.md`. Boundary model and repair process.
- `reference/task-seeds.md`. Ordered tasks for one repair.

```text
repairing-hook-boundaries/
├── SKILL.md
└── reference/
    └── task-seeds.md
```
