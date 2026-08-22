---
description: Converging cleanup loop - repeat /simplify until clean, then repeat /code-review --fix until clean
argument-hint: [PR URL, branch, or blank for the current diff]
---

Run the converging cleanup loop on the target: `$ARGUMENTS` (blank means the
current branch's diff). Each phase invokes an existing skill with the Skill
tool and repeats it until a pass returns zero new findings.

Use `rules/asd-ste100-language.md` for user-facing wording. Keep the loop's
cleanup, verification, commit, push, and finish-report fields.

## Phase A — loop /simplify

1. Invoke the `simplify` skill on the target (the same review the user gets
   from `/simplify <target>`). Let it run its 4-lens fan-out and apply its
   fixes.
2. After each pass: run the scoped test suite (test files beside the touched
   code, not the full repo suite), commit once (`git commit -F <file>`, body
   written with the Write tool, Co-Authored-By line, 10-minute timeout — the
   pre-commit gate runs its own tests), and push to the PR head branch. The PR
   stays draft.
3. Repeat the invocation. **Skips are sticky:** carry every adjudicated skip
   forward into the next pass as "already adjudicated — do not re-report: ..."
   context, or the loop never converges.
4. Phase A converges when a full pass returns zero new findings, or when a
   pass's new findings are all nits — doc phrasing, naming, comment altitude,
   or any fix below a behavior change. On a nit-only pass: apply the fixes,
   test, commit, push, and stop with no confirming pass. When the previous
   pass changed only a line or two, a single combined-lens confirmation agent
   may serve as the final pass.

## Phase B — loop /code-review low --fix

1. Invoke the `code-review` skill with arguments `low --fix` on the same
   target. Let it report findings and apply its fixes.
2. After any pass that changed files: test, commit, push as in Phase A.
3. Repeat until a pass reports zero findings, or until a pass reports only
   nits — then fix, test, commit, push, and stop with no confirming pass.
   Phase B usually converges in one pass when Phase A ran first.

## Finish

Report: passes run per phase, commits pushed with hashes, fixes applied, and
the standing skip list with reasons.

## Constraints (observed under headless runs)

- Run this loop in the main session. A wrapper subagent cannot see the
  `code-review` skill, and a nested agent's own subagent reports route to the
  main session instead of back to it.
- Scope test runs to the touched files; a full-suite run can outlive one
  foreground tool call.
- A hung or newly slow test suite is a finding to investigate, not an
  inconvenience.
