# split-pr task seeds

Register each item on the host task tool at skill start. Mark complete with evidence.

1. Resolve PR number and repo; refuse if closed/missing.
2. Run `scripts/analyze_pr.py --pr <N>`; save plan JSON path.
3. Refine buckets if `other` or warnings fire; keep every path.
4. Run `scripts/verify_plan.py --plan <path>`; require `is_valid`.
5. Print decision brief in chat (re-buckets, slice table, merge order) before any approval control.
6. Propose via `AskUserQuestion` (approve / local-only / abort).
7. On approve: dry-run optional, then `execute_split.py` with push+draft PRs (or local-only if requested).
8. Report merge order, branch names, PR URLs; leave source branch unchanged.
