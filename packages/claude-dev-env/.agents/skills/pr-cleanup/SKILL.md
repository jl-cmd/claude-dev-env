---
name: pr-cleanup
description: Refine a pull request, then run the final simplify and code-review loop. Use when the user asks for /pr-cleanup or full PR cleanup.
---

# PR Cleanup

Run `pr-refinement`, then run `sr-loop` on its resulting pull request or stack.

## Workflow

1. Resolve the target pull request and use its head worktree.
2. Run `pr-refinement`. It owns extraction, capability naming, in-place updates, and a required replacement stack.
3. Run `sr-loop` on every resulting pull request. Apply findings, run scoped tests, commit, and push each validated change.
4. Keep every pull request draft. Keep merge authority with the user.

## Finish report

- Pull request or stack URLs.
- `pr-refinement` outcome.
- `sr-loop` passes, commits, and validation results.
- Remaining hard block, or `null`.
