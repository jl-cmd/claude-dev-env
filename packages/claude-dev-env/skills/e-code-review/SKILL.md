---
name: e-code-review
description: >-
  Max-recall code review at a selectable effort level (low, xhigh, max), with an optional loop mode for max.
  Triggers: /e-code-review, /e-code-review low, /e-code-review xhigh,
  /e-code-review max, /e-code-review max loop.
---

# e-code-review

**Core principle:** One review procedure per effort level (`low`, `xhigh`, `max`), each a separate reference file; this hub only routes to the right one.

## Gotchas

- `low`'s procedure spawns no subagents at all (one diff read, one findings pass) — its whole point is a fast, single-pass review. Don't add agent spawns to `low`; that defeats the point.

## When this skill applies

Triggers: `/e-code-review <level> [loop]` where `<level>` is `low`, `xhigh`, or `max`. `loop` is optional and applies to the `max` procedure.

**Refusal cases — first match wins:**

- **No level given, or an unrecognized level.** Respond exactly: `Which effort level — low, xhigh, or max?`
- **`loop` with `low` or `xhigh`.** Respond exactly: `The loop argument is only supported with max.`

## The process

1. Read the level argument (`low` / `xhigh` / `max`) and optional `loop` flag. Apply the refusal cases above before anything else, including rejecting `loop` unless the level is `max`.
2. Load the matching file — `reference/low.md`, `reference/xhigh.md`, or `reference/max.md` — and follow its procedure exactly as written.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This hub — routing by effort level, refusal cases |
| `reference/xhigh.md` | Full xhigh-effort review procedure (defined) |
| `reference/max.md` | Full max-effort review procedure (defined) |
| `reference/low.md` | Fast single-pass low-effort review procedure (defined) |

## Folder map

- `SKILL.md` — hub: routing, refusals.
- `reference/` — one procedure file per effort level.
