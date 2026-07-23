---
name: e-code-review
description: >-
  Max-recall code review at a selectable effort level (low, xhigh, max), with an
  optional auto-execute loop for any level. Triggers: /e-code-review,
  /e-code-review low, /e-code-review xhigh, /e-code-review max,
  /e-code-review <level> loop.
---

# e-code-review

**Core principle:** One review procedure per effort level (`low`, `xhigh`, `max`), each a separate reference file; this hub routes to the right one. Optional `loop` convergence is shared in `reference/loop.md` and applies to every level.

## Gotchas

- `low`'s procedure spawns no subagents at all (one diff read, one findings pass) — its whole point is a fast, single-pass review. Don't add agent spawns to `low`; that defeats the point.
- `loop` is auto-execute for **any** level: after verified findings, fix nits / stop on bugs without asking. Load `reference/loop.md` and follow it.

## When this skill applies

Triggers: `/e-code-review <level> [loop]` where `<level>` is `low`, `xhigh`, or `max`. `loop` is optional and applies to **every** level.

**Refusal cases — first match wins:**

- **No level given, or an unrecognized level.** Respond exactly: `Which effort level — low, xhigh, or max?`

## The process

1. Read the level argument (`low` / `xhigh` / `max`) and optional `loop` flag. Apply the refusal cases above before anything else.
2. Load the matching file — `reference/low.md`, `reference/xhigh.md`, or `reference/max.md` — and follow its procedure exactly as written. That procedure is one review cycle for the selected level.
3. If `loop` is set, after that cycle yields its findings set, load `reference/loop.md` and follow it. Each re-review re-runs the **same** level procedure from step 2. If `loop` is not set, return that cycle's findings and stop.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This hub — routing by effort level, refusals, loop dispatch |
| `reference/loop.md` | Shared auto-execute loop for any effort level |
| `reference/xhigh.md` | Full xhigh-effort review procedure (defined) |
| `reference/max.md` | Full max-effort review procedure (defined) |
| `reference/low.md` | Fast single-pass low-effort review procedure (defined) |

## Folder map

- `SKILL.md` — hub: routing, refusals, loop dispatch.
- `reference/` — one procedure file per effort level, plus shared `loop.md`.
