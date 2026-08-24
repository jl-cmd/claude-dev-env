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

## Promotion gates

Run preflight work in isolated worktrees from the recorded parent SHA. Apply selected changes in the parent worktree.

Before promoting a child, merge the exact parent-ready SHA. Prove that SHA is an ancestor of the child head. Rerun the child tests, `e-simplify`, and `e-code-review` after the merge.

Use `reference/task-seeds.md` and `reference/process-inventory.md` to record promotion evidence.

## Finish report

- Pull request or stack URLs.
- `pr-refinement` outcome.
- `sr-loop` passes, commits, and validation results.
- Parent-ready and child-ready SHAs when a child is promoted.
- Remaining hard block, or `null`.
