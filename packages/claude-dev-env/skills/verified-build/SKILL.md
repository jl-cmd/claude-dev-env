---
name: verified-build
description: >-
  Runs a code task through the two-phase verified workflow: scoped coder
  agents write the changes (consulting the tool-less code-advisor when
  stuck on a decision), then a fresh-context code-verifier agent re-derives
  and runs every check itself. The verifier's fenced verdict is minted by
  the verifier_verdict_minter hook and unlocks the verified_commit_gate for
  git commit/push. Use for feature implementations, refactors, and bug
  fixes that land behind verification. Triggers: 'verified build', 'run
  this verified', 'two-phase build', 'build and verify', 'verified
  implementation'.
---

# Verified Build

Two phases, hook-enforced: coders write, a fresh-context verifier grades, and `git commit`/`git push` open only on a clean verdict bound to the live change surface.

## Workflow

Copy this checklist and check items off as you go:

- [ ] **Record baselines.** Before any coder runs: the test command and its exact failure set, plus any other gates the repo names. Scope the test command to the modules the task touches (their test files plus tests importing the changed modules); record a full-suite baseline only when the assignments span multiple modules or multiple coders. The verifier compares against these.
- [ ] **Scope assignments.** Split the task into file-disjoint assignments; write each as a task text with named checks.
- [ ] **Spawn coders.** One agent per assignment (`clean-coder` or Sonnet). Tell each: on a decision it can't reasonably solve, consult the tool-less `code-advisor` agent — it returns a plan, a correction, or a stop signal — then resume.
- [ ] **Settle the tree.** After coders finish: run formatters and any file-rewriting hooks, stage nothing, change nothing more.
- [ ] **Spawn the verifier last.** Agent tool, `subagent_type: "code-verifier"`, with the task texts, the diff scope, and the recorded baselines. When it stops, the SubagentStop hook mints its verdict.
- [ ] **Repair only reported findings.** On a failing verdict, spawn repair agents scoped to the findings, then re-spawn the verifier. Repeat until clean.
- [ ] **Land right away.** One commit, push, draft PR — before anything else touches a file.

## Gotchas

- Any file change after the verifier stops moves the surface hash and re-locks the gate — formatter rewrites included. Settle the tree first; land right after the clean verdict.
- The verdict covers the whole branch surface (merge base to work tree, untracked files included). There is no "verify just my part."
- The verifier must end with a ```` ```verdict ```` fence. No fence means nothing is minted and the gate stays closed.
- The minter keys on the agent type string `code-verifier` — spawning the same prompt under another agent type mints nothing.
- A surface whose every change is a docs/image file (by extension), a Python file whose docstring-stripped AST is unchanged (docstring-, comment-, or formatting-only Python edits), or a pytest test file (`test_*.py`, `*_test.py`, `conftest.py`) is exempt automatically; skip the verifier for those. Comment-only edits in non-Python files are not exempt.
- Record the test baseline before coders start. Without the exact pre-existing failure set, new breakage hides inside old noise.
