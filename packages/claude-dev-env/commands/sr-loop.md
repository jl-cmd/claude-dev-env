---
description: Converging cleanup loop - /simplify passes until clean, then a code-review fix pass
argument-hint: [PR URL, branch, or blank for the current diff]
---

Run the converging cleanup loop on the target: `$ARGUMENTS` (blank means the
current branch's diff, `git diff @{upstream}...HEAD` plus `git diff HEAD`).
For a PR URL or number, check out its head branch in a worktree under
`.claude/worktrees/` and review `git diff origin/<base>...HEAD` there.

## Phase A — simplify passes until clean

1. Launch 4 parallel review subagents via the Agent tool in a single message,
   one lens each: **reuse** (new code re-implementing an existing repo helper —
   name the helper), **simplification** (redundant or derivable state,
   copy-paste with variation, deep nesting, dead code — name the simpler form),
   **efficiency** (redundant computation or I/O, sequentialized independent
   work, hot-path or startup blocking, closure-built long-lived objects — name
   the cheaper form), **altitude** (special cases layered on shared
   infrastructure instead of generalizing the mechanism — name the deeper fix).
   Each agent gets the worktree path, the diff command, and returns findings
   (`file`, `line`, `summary`, `cost`, `fix`) or "no findings". Each agent
   prompt carries: "Read-only; do NOT hunt correctness bugs. Never use bash rm
   in any form; delete scratch files with the PowerShell tool
   (`Remove-Item -Recurse -Force -Confirm:$false <absolute path>`) or leave
   them in the OS temp dir."
2. Dedup findings that point at the same line or mechanism. Apply each fix;
   skip any that would change intended behavior, need work well outside the
   reviewed diff, or is a false positive — record every skip with a one-line
   reason.
3. Run the scoped test suite (the test files beside the touched code), not the
   full repo suite — a full run can outlive a single foreground tool call. A
   hung or newly slow suite is a finding to investigate, not an inconvenience.
4. Commit once per pass: body via `git commit -F <file>` written with the Write
   tool, ending with the repo's Co-Authored-By line. Give the commit call a
   10-minute timeout — the pre-commit gate runs its own test suite. Push to the
   PR head branch; the PR stays draft.
5. Repeat with fresh agents. **Skips are sticky:** every later pass's agent
   prompts list each adjudicated skip as "do not re-report: ..." — without
   this the loop never converges.
6. Converge when a full pass returns zero new findings. When the previous pass
   changed only a line or two, one combined-lens confirmation agent may serve
   as the final pass.

## Phase B — code-review fix passes until clean

1. Read the updated diff yourself (skip test/fixture hunks). Flag at most 4
   hunk-visible runtime-correctness bugs: inverted condition, off-by-one,
   absent-value deref, removed guard, falsy-zero check, missing await,
   wrong-variable copy-paste, swallowed error. No style, naming, or perf.
2. Apply fixes under the same skip rules; test, commit, push as in Phase A.
3. Repeat until a pass reports zero findings. Phase B usually converges in one
   pass when Phase A ran first.

## Finish

Report: passes run per phase, commits pushed with hashes, fixes applied,
and the standing skip list with reasons.

## Constraints observed under headless runs

- Run the whole loop in the main session. Delegating it to one wrapper agent
  breaks the fan-out: a nested agent's subagent reports route to the main
  session, not back to the wrapper.
- If a fan-out must ever run inside a subagent, spawn the children
  synchronously (`run_in_background: false`).
