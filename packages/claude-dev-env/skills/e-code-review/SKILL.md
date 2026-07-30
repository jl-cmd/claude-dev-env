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

- **`low` stays single-pass.** No subagents, no full-file reads: one read pass per target item, one findings pass.
- **`medium` favors precision, `xhigh` favors recall.** At `medium` (8 angles) surface only findings a maintainer would act on. At `xhigh` (10 angles plus a gap sweep) a single non-REFUTED vote carries the finding; do not drop on uncertainty.
- **Every retained finding carries `severity` and `verdict`.** Severity is one of `blocker`, `high`, `medium`, `low`, `nit`. Verdict is `CONFIRMED` or `PLAUSIBLE`. Drop REFUTED candidates; never emit an unclassified retained finding.
- **`--fix` applies findings once.** Load `reference/fix.md` and follow it — it owns the fix agent, the code-rules gate, skip logging, and outcome reporting. Commits are lead-owned; fix agents never commit or push.
- **`loop` never asks.** A round with bug findings validates them with an advisor, fixes, and re-reviews. Terminals are exactly `clean`, `nits_fixed`, `blocked_at_cap`, and `advisor_blocked`. Cap is three distinct reviewed heads; a new head increments the count once, a re-review of the same head does not. Load `reference/loop.md` and follow it.
- **`--fix` and `loop` combine.** With both, each loop round runs the level file, and the round's fixing happens inside `reference/loop.md`'s gate sequence, which loads `reference/fix.md` for the mechanics. There is no separate fix pass around the round.

## When this skill applies

Triggers: `/e-code-review <level> [--fix] [loop]`. `<level>` is `low`, `medium`, or `xhigh`. `--fix` and `loop` are each optional and may be used together.

**Refusal — first match wins:**

- **No level, or an unknown level.** Respond exactly: `Which effort level — low, medium, or xhigh?`

## The process

1. Read `<level>` and the optional `--fix` and `loop` flags. Apply the refusal first.
2. Load `reference/low.md`, `reference/medium.md`, or `reference/xhigh.md`. Run that file as one review cycle, ending in its structured findings report.
3. If `--fix` is set and `loop` is not set, load `reference/fix.md` and apply it to that cycle's findings. This path has no commit step: the fixes stay uncommitted in the working tree for the user to review and commit.
4. If `loop` is set, load `reference/loop.md` and follow it with that cycle's findings still unfixed. Round 1's findings are the ones step 2 already produced; from the second round on, the round re-runs that same level file end to end. End to end means the level file's review phases, up to and including its findings report — not its *Looping* section, which hands control to `loop.md` and would re-enter the loop the round is already inside. `loop.md`'s gate sequence owns when the round fixes.
5. Without `--fix` or `loop`, return the cycle findings and stop.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Route by level; dispatch `--fix` and `loop` |
| `reference/low.md` | low review procedure — 1 diff pass per target item, no verify |
| `reference/medium.md` | medium review procedure — 8 angles, 1-vote verify |
| `reference/xhigh.md` | xhigh review procedure — 10 angles, 1-vote verify, gap sweep |
| `reference/fix.md` | Fix application, code-rules gate, skip logging, outcome reporting |
| `reference/loop.md` | Repeat review/fix rounds until clean |

## Folder map

- `SKILL.md` — route and dispatch.
- `reference/` — one procedure per level, plus `fix.md` and `loop.md`.
