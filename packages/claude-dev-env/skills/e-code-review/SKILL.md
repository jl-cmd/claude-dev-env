---
name: e-code-review
description: >-
  Max-recall code review at a selectable effort level (low, medium, xhigh), with
  optional auto-fix and an auto-execute loop for any level. Triggers:
  /e-code-review, /e-code-review low, /e-code-review medium, /e-code-review
  xhigh, /e-code-review <level> --fix, /e-code-review <level> loop.
---

# e-code-review

**Pick a level, run that review, optionally fix and loop.** Each level has its own procedure file. Fix application lives in `reference/fix.md`; repeat-until-clean lives in `reference/loop.md`.

## Gotchas

- **`low` stays single-pass.** Do not spawn subagents. One diff read, one findings pass.
- **`medium` favors precision, `xhigh` favors recall.** At `medium` (8 angles) surface only findings a maintainer would act on. At `xhigh` (10 angles plus a gap sweep) a single non-REFUTED vote carries the finding; do not drop on uncertainty.
- **`--fix` applies findings once.** Load `reference/fix.md` and follow it — it owns the fix agent, the commit gate, skip logging, and outcome reporting.
- **`loop` never asks.** Each round validates its bug findings with an advisor, fixes, and re-reviews. Load `reference/loop.md` and follow it.
- **`--fix` and `loop` combine.** With both, each loop round runs the level file, and the round's fixing happens inside `reference/loop.md`'s gate sequence, which loads `reference/fix.md` for the mechanics. There is no separate fix pass around the round.

## When this skill applies

Triggers: `/e-code-review <level> [--fix] [loop]`. `<level>` is `low`, `medium`, or `xhigh`. `--fix` and `loop` are each optional and may be used together.

**Refusal — first match wins:**

- **No level, or an unknown level.** Respond exactly: `Which effort level — low, medium, or xhigh?`

## The process

1. Read `<level>` and the optional `--fix` and `loop` flags. Apply the refusal first.
2. Load `reference/low.md`, `reference/medium.md`, or `reference/xhigh.md`. Run that file as one review cycle, ending in its structured findings report.
3. If `--fix` is set and `loop` is not set, load `reference/fix.md` and apply it to that cycle's findings.
4. If `loop` is set, load `reference/loop.md` and follow it with that cycle's findings still unfixed. Each round re-runs the same level file from step 2; `loop.md`'s gate sequence owns when the round fixes.
5. Without `--fix` or `loop`, return the cycle findings and stop.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Route by level; dispatch `--fix` and `loop` |
| `reference/low.md` | low review procedure — 1 diff pass, no verify |
| `reference/medium.md` | medium review procedure — 8 angles, 1-vote verify |
| `reference/xhigh.md` | xhigh review procedure — 10 angles, 1-vote verify, gap sweep |
| `reference/fix.md` | Fix application, commit gate, skip logging, outcome reporting |
| `reference/loop.md` | Repeat review/fix rounds until clean |

## Folder map

- `SKILL.md` — route and dispatch.
- `reference/` — one procedure per level, plus `fix.md` and `loop.md`.
