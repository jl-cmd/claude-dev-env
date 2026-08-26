# PR cleanup task seeds

Register each numbered item as one session task before work starts. Complete
each task with evidence from the stated gate.

1. Resolve the target PR, repository, parent head SHA, and child boundary.
2. Create isolated preflight worktrees from the immutable parent preflight SHA.
3. Run the shared-extraction, capability-name, `e-simplify`, and `e-code-review` preflight streams in parallel when available.
4. Record each stream's worktree, base SHA, findings, proposed patch, and validation evidence.
5. Keep parent merge, rebase, push, and Ready operations unavailable during preflight.
6. Select, apply, validate, or exactly disposition every actionable preflight finding in the one-agent parent cleanup worktree.
7. Run parent scoped tests and cleanup/review confirmation checks.
8. Promote the parent to Ready and record the exact remote `parent_ready_sha`.
9. When `.claude/skills/pr-summarizer/SKILL.md` exists in the repository under cleanup, run that skill on the parent and post the gist preview comment; otherwise record `N/A`.
10. Create the child from its intended pre-parent base and merge the exact `parent_ready_sha`.
11. Prove `parent_ready_sha` is an ancestor of the child head and record the exit code.
12. Reapply every relevant preflight fix to the child.
13. Run child scoped tests on the new child head.
14. Rerun `e-simplify` and `e-code-review` on the new child head.
15. Promote the child to Ready after all child evidence passes.
16. When the repository ships `pr-summarizer` and the child is in scope, run it on the child and post the gist preview comment; otherwise record `N/A`.
17. Write the finish report with SHAs, evidence, summary preview URLs, states, and hard blocks.
