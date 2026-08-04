---
description: Converging cleanup loop - repeat /simplify until clean, then repeat /code-review --fix until clean
argument-hint: [PR URL, branch, or blank for the current diff]
---

Run the converging cleanup loop on the target: `$ARGUMENTS` (blank means the
current branch's diff). Each phase invokes an existing skill with the Skill
tool and repeats it until a pass returns zero new findings.

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
4. Phase A converges when a full pass returns zero new findings. When the
   previous pass changed only a line or two, a single combined-lens
   confirmation agent may serve as the final pass.

## Phase B — loop /code-review low --fix

1. Run the real built-in `code-review` command through a headless subprocess
   in the target worktree:

   ```
   claude -p "/code-review low --fix" --max-turns 40
   ```

   The skill's `disable-model-invocation` flag blocks only the Skill tool; in
   a `-p` run the slash command arrives as user input and loads normally
   (verified live). Give the call a 10-minute timeout and read its final text
   for the findings and applied fixes. Fallback if the headless run fails:
   invoke the `e-code-review` skill with `low --fix` through the Skill tool —
   same review-and-fix contract, no invocation restriction.
2. After any pass that changed files: test, commit, push as in Phase A.
3. Repeat until a pass reports zero findings. Phase B usually converges in one
   pass when Phase A ran first.

## Finish

Report: passes run per phase, commits pushed with hashes, fixes applied, and
the standing skip list with reasons.

## Constraints (observed under headless runs)

- Run this loop in the main session. A nested agent's own subagent reports
  route to the main session instead of back to its spawner.
- Scope test runs to the touched files; a full-suite run can outlive one
  foreground tool call.
- A hung or newly slow test suite is a finding to investigate, not an
  inconvenience.
