# verified-build

Runs a code task through the two-phase verified workflow: scoped coder agents write the changes, then a fresh-context `code-verifier` agent re-derives and runs every check itself.

**Trigger:** "verified build", "run this verified", "two-phase build", "build and verify", "verified implementation".

## Purpose

Ensures that `git commit`/`git push` open only after a clean, hook-minted verifier verdict bound to the live change surface. The `verified_commit_gate` hook blocks commits and pushes until a verdict covers the current branch diff.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | The complete skill — workflow checklist, gotchas. No companion files. |

## Workflow (copy-this checklist)

- [ ] Record baselines (test command + exact failure set) before coders start
- [ ] Scope assignments into file-disjoint tasks with named checks
- [ ] Spawn one `clean-coder` (or Sonnet) agent per assignment; each consults `code-advisor` on decisions it cannot resolve
- [ ] Settle the tree after coders finish (run formatters, stage nothing)
- [ ] Spawn `code-verifier` (fresh context) with task texts, diff scope, and baselines
- [ ] Repair only reported findings; re-spawn verifier after each repair
- [ ] Land in one commit + push + draft PR as soon as verdict is clean

## Conventions

- Any file change after the verifier stops re-locks the gate — run formatters before spawning the verifier.
- The verifier must end with a ` ```verdict ` fence; the `verifier_verdict_minter` hook mints the verdict from that fence.
- The minter keys on agent type string `code-verifier` — the same prompt under another agent type mints nothing.
- Docs/image-only diffs, docstring-only Python diffs, and pytest test files (`test_*.py`, `*_test.py`, `conftest.py`) are exempt from the gate automatically.
- Record the test baseline before coders start; without it, new breakage hides inside old noise.
