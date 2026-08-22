---
name: pr-cleanup
description: >-
  Clean a PR end-to-end with one coding agent: shared-extraction-audit,
  name-by-capability-audit, sr-loop, then small-cl — apply and validate fixes
  as they return. Use when the user asks for /pr-cleanup or full PR cleanup
  (place, name, converge, then shrink).
---

# PR cleanup

One coding agent cleans a pull request end-to-end: put code in the right place,
name it for what it does, run the converging cleanup loop, then shrink the
change into a reviewable size.

This skill is host-neutral. Any coding agent that can edit the PR head, run
scoped tests, and invoke the composed skills may run it.

## When to use

- `/pr-cleanup <PR>` or “run pr-cleanup on this PR”
- A PR needs extraction + naming + sr-loop + a smaller reviewable slice in one pass

## Inputs

- Target: PR URL, number, or branch (required). Missing → ask:
  `Give a GitHub PR number or URL for pr-cleanup.`
- Repo: take from the PR URL when given; otherwise the user’s default monitored repo

## Composition (run in this order)

| Step | Skill | Role |
|------|--------|------|
| 1 | `shared-extraction-audit` | Wrong *place* (workflow package vs shared library) |
| 2 | `name-by-capability-audit` | Wrong *name* (driver word on reusable capability) |
| 3 | `sr-loop` / `e-simplify` then `e-code-review` | Converging simplify + high-effort review with `--fix` |
| 4 | `small-cl` | Split / shrink into a focused reviewable PR |

All four run under **one coding agent session** on the same worktree / PR head.
For sr-loop advisor consults, bind `team-advisor` as a second session at equal
tier when the host supports it (see `team-advisor` and the advisor docs).

## Fix-as-you-go (required)

Some of these skills can report without changing code. For **pr-cleanup**, that
is not enough:

1. **Stream findings** — as each audit/loop returns an item (offense, rename,
   simplify fix, review finding), treat it as work to do now, not a backlog.
2. **Apply the fix** on the PR head (or the first small-cl increment if already
   splitting) before moving on to the next item when practical.
3. **Validate** after each applied fix: scoped tests beside touched files (or
   `py_compile` / package tests when there is no adjacent suite). No test theater.
4. **Commit + push** after each validated changing pass (one concern per commit
   when possible; keep the PR draft).
5. **Do not** finish with an audit-only report while known P0/P1 fixes sit
   unapplied — either fix them or hard-block with why.

If the user says **audit-only**, stop after reports and skip apply / small-cl.

## Process

1. Resolve PR → convert to draft if needed; clean worktree of the PR head;
   never mark ready for review.
2. Run the four composed skills in order on that head:
   - `shared-extraction-audit` in the **implement** band (not audit-only)
   - `name-by-capability-audit`; apply clear rename directions (or ones the user
     already approved), noting rename direction in the commit message
   - `sr-loop`: Phase A `e-simplify`, Phase B `e-code-review` at **xhigh** with
     `--fix` (not the default low); consult `team-advisor` before the first
     write and after writes + validation
   - Apply fixes as each pass returns findings; validate → commit → push
3. After the loop converges (or nits-only stop): run **small-cl** — identify the
   first coherent reviewable increment; if the PR is still too wide, split or
   retitle/scope per small-cl (do not invent extra PRs unless the user asked).
4. Return the finish report below. Merge-ready email / chat delivery is owned by
   the caller (for example a PR monitor host), not this skill.

## Hard rules

- No test theater.
- Real spawn/behavior validation when the PR claims an external binary path.
- Prefer cleanup; functional only for correctness. Label each commit
  `cleanup` vs `functional`.
- Keep the PR draft. Never mark ready for review during this skill.
- Extraction before rename when both apply to the same symbol (move, then name
  the new home).
- small-cl last — shrink only after place / name / cleanup are settled enough
  that the slice is honest.

## Finish report

- PR / repo / starting_sha / ending_sha
- Per step: extraction findings applied, naming violations applied, sr-loop
  passes + commits, small-cl outcome (kept / split plan)
- `commits_pushed` with cleanup|functional labels
- `validation_ran` + outcomes
- `hard_block` or null
- `draft_still: true`
