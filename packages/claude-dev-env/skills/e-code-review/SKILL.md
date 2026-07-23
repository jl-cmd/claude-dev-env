---
name: e-code-review
description: >-
  Max-recall code review at a selectable effort level (low, xhigh, max), with an
  optional auto-execute loop for any level. Triggers: /e-code-review,
  /e-code-review low, /e-code-review xhigh, /e-code-review max,
  /e-code-review <level> loop.
---

# e-code-review

**Pick a level, run that review, optionally loop.** Each level has its own procedure file. Shared fix-and-re-review lives in `reference/loop.md`.

## Gotchas

- **`low` stays single-pass.** Do not spawn subagents. One diff read, one findings pass.
- **`loop` never asks.** After findings, fix nits or stop on bugs. Load `reference/loop.md` and follow it.

## When this skill applies

Triggers: `/e-code-review <level> [loop]`. `<level>` is `low`, `xhigh`, or `max`. `loop` is optional on every level.

**Refusal — first match wins:**

- **No level, or an unknown level.** Respond exactly: `Which effort level — low, xhigh, or max?`

## The process

1. Read `<level>` and the optional `loop` flag. Apply the refusal first.
2. Load `reference/low.md`, `reference/xhigh.md`, or `reference/max.md`. Run that file as one review cycle.
3. If `loop` is set, load `reference/loop.md` and follow it. Each re-review re-runs the same level file from step 2. Without `loop`, return the cycle findings and stop.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Route by level; dispatch `loop` |
| `reference/loop.md` | Auto-execute fix cycle for any level |
| `reference/xhigh.md` | xhigh review procedure |
| `reference/max.md` | max review procedure |
| `reference/low.md` | low review procedure |

## Folder map

- `SKILL.md` — route and dispatch.
- `reference/` — one procedure per level, plus `loop.md`.
