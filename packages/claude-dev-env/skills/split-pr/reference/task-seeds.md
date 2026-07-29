# split-pr task seeds

Register each item on the host task tool at skill start. Mark complete with evidence.

1. Resolve PR number and repo; refuse if closed/missing.
2. Run `scripts/analyze_pr.py --pr <N>`; save plan JSON path.
3. Refine buckets if `other` or warnings fire; keep every path.
4. Run `scripts/verify_plan.py --plan <path>`; require `is_valid`.
5. Print decision brief in chat (re-buckets, slice table, merge order) before any approval control.
6. Propose via `AskUserQuestion` (approve / local-only / abort).
7. On approve: dry-run optional, then `execute_split.py` with push+draft PRs (or local-only if requested). Execute runs pytest `--collect-only` on cumulative stack test modules after each slice commit; on collection failure, re-bucket (definitions earlier or co-located with tests), re-verify, and re-execute — do not push a non-collecting stack.
8. After successful push+create with a draft URL for each planned slice: post a family-tree comment on **each** child PR (source, merge order, full linked list, mark this PR) via `--body-file`. Apply discovery labels `split-pr` and `split-stack:<source>` on the source PR and every child. Then supersede the source PR — comment merge order + child URLs, then `gh pr close`. Skip family-tree, stack labels, and supersede when partial, local-only, or create-prs off; skip supersede when atomic or already superseded. Leave the source branch on the remote.
9. Report merge order, branch names, PR URLs, `family_tree`, `stack_labels`, and supersede outcome; leave source branch unchanged.
10. Run split-further loop ([split-further-loop.md](split-further-loop.md)): BFS re-split each draft without AskUserQuestion until stop reasons drain the queue.
