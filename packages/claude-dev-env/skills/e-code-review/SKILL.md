---
name: e-code-review
description: >-
  Max-recall code review at a selectable effort level (low, xhigh, max), with an
  optional auto-execute loop for any level. Triggers: /e-code-review,
  /e-code-review low, /e-code-review xhigh, /e-code-review max,
  /e-code-review <level> loop.
---

# e-code-review

**Core principle:** One review procedure per effort level (`low`, `xhigh`, `max`), each a separate reference file; this hub routes to the right one and owns optional `loop` convergence for every level.

## Gotchas

- `low`'s procedure spawns no subagents at all (one diff read, one findings pass) — its whole point is a fast, single-pass review. Don't add agent spawns to `low`; that defeats the point.
- `loop` is auto-execute for **any** level: after verified findings, fix nits / stop on bugs without asking. See [Optional loop mode](#optional-loop-mode).

## When this skill applies

Triggers: `/e-code-review <level> [loop]` where `<level>` is `low`, `xhigh`, or `max`. `loop` is optional and applies to **every** level.

**Refusal cases — first match wins:**

- **No level given, or an unrecognized level.** Respond exactly: `Which effort level — low, xhigh, or max?`

## The process

1. Read the level argument (`low` / `xhigh` / `max`) and optional `loop` flag. Apply the refusal cases above before anything else.
2. Load the matching file — `reference/low.md`, `reference/xhigh.md`, or `reference/max.md` — and follow its procedure exactly as written. That procedure is one review cycle for the selected level.
3. If `loop` is set, after that cycle yields its findings set, apply [Optional loop mode](#optional-loop-mode). Each re-review re-runs the **same** level procedure from step 2. If `loop` is not set, return that cycle's findings and stop.

## Optional loop mode

When the hub invocation includes `loop`, that invocation authorizes action. After the level procedure produces a verified findings set, execute the matching branch immediately. Do not ask whether to fix, which nits to keep, whether to commit or push, or whether to re-review. Do not open a plan fork or end the turn on a recommendation. Report progress only while working; the next user-facing stop is a terminal outcome below.

**Severity for loop branches**

- Prefer the finding's verified `severity` when the level emits one (`bug` or `nit`).
- A finding is a `nit` only when its verified severity is `nit`. Runtime-correctness, security, data-loss, compatibility, and every other non-nit finding is a `bug`.
- When the level does not emit severity (for example `low`), treat every non-empty finding as a `bug`.

**Terminal outcomes** — repeat the level's review/fix cycle until one of these:

- **Clean** — review returns no findings (`[]` or `(none)`). Mark ready: post the proof-of-work PR comment when the target is a PR, then run `gh pr ready` for a draft PR; otherwise state ready.
- **Nits only** — every surviving finding is severity `nit`. Fix all of them on the PR branch worktree (or the review target), run required checks, commit (one commit per loop round), push, and run another full review at the **same** effort level on the new head. Repeat until clean, then mark ready as above.
- **Any bug** — any surviving finding is severity `bug`. Return every validated finding (bugs and nits), stop the loop, do not mark ready, and do not ask whether to continue; wait for a new user instruction.

Do not discard findings to force a ready outcome. Without `loop`, run one review at the selected level and return every validated finding; do not apply this convergence behavior.

### Loop autonomy

No mid-loop confirmation questions, “should I fix these?”, “want me to push?”, or option menus. Auto-fix only verified findings on the review target; do not expand into deferred PR-body follow-ups or unrelated refactors. House git gates still apply (draft PR, verified commit, one commit per round, proof-of-work when required)—satisfy them by doing the steps, not by asking permission.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This hub — routing by effort level, refusals, shared `loop` mode |
| `reference/xhigh.md` | Full xhigh-effort review procedure (defined) |
| `reference/max.md` | Full max-effort review procedure (defined) |
| `reference/low.md` | Fast single-pass low-effort review procedure (defined) |

## Folder map

- `SKILL.md` — hub: routing, refusals, loop.
- `reference/` — one procedure file per effort level.
