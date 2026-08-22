---
name: "source-command-sr-loop"
description: "Converging cleanup loop: repeat /simplify until clean, then repeat /code-review --fix until clean"
---

# source-command-sr-loop

Use this skill when the user asks to run the migrated source command `sr-loop`.

## Command Template

Run the converging cleanup loop on the target the user names (a PR URL,
a branch, or blank for the current branch's diff). Each phase invokes an
existing skill and repeats it until a pass returns zero new findings.

### Phase A — loop simplify

1. Invoke the `simplify` skill (or its local equivalent, e.g. `e-simplify`)
   on the target. Let it run its 4-lens review fan-out (reuse,
   simplification, efficiency, altitude) and apply its fixes.
2. After each pass: run the scoped test suite (test files beside the touched
   code, not the full repo suite), commit once (commit body via
   `git commit -F <file>`, 10-minute timeout — the pre-commit gate runs its
   own tests), and push to the PR head branch. The PR stays draft.
3. Repeat the invocation. Skips are sticky: carry every adjudicated skip
   forward into the next pass as "already adjudicated — do not re-report: ..."
   context, or the loop never converges.
4. Phase A converges when a full pass returns zero new findings. When the
   previous pass changed only a line or two, a single combined-lens
   confirmation agent may serve as the final pass.

### Phase B — loop code-review with fixes

1. Run the real code-review command through a headless subprocess in the
   target worktree: `claude -p "/code-review low --fix" --max-turns 40` with a
   10-minute timeout, reading its final text for findings and applied fixes.
   (The skill's `disable-model-invocation` flag blocks only programmatic tool
   starts; a `-p` prompt arrives as user input and loads normally.) Fallback
   when the headless run fails: invoke the `e-code-review` skill with
   `low --fix` — same review-and-fix contract, no invocation restriction.
2. After any pass that changed files: test, commit, push as in Phase A.
3. Repeat until a pass reports zero findings. Phase B usually converges in
   one pass when Phase A ran first.

### Finish

Report: passes run per phase, commits pushed with hashes, fixes applied, and
the standing skip list with reasons.

### Constraints (observed under headless runs)

- Run this loop in the main conversation. A wrapper subagent cannot see the
  review skills, and a nested agent's own subagent reports route to the main
  conversation instead of back to it.
- Scope test runs to the touched files; a full-suite run can outlive one
  foreground tool call.
- A hung or newly slow test suite is a finding to investigate, not an
  inconvenience.
