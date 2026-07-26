# split-pr task seeds

Register each item on the host task tool at skill start. Mark complete with evidence.

1. Resolve PR number and repo; refuse if closed/missing.
2. Run `scripts/analyze_pr.py --pr <N>`; save plan JSON path.
3. Refine buckets if `other` or warnings fire; keep every path. A plan carrying `threshold_note` (warning `parent_fits_review_budget_split_optional`, one `whole-pr` slice) means the parent already fits review budget — confirm the user still wants the split.
4. Run `scripts/verify_plan.py --plan <path>`; require `is_valid`.
5. Print decision brief in chat (re-buckets, slice table, merge order) before any approval control.
6. Propose via `AskUserQuestion` (approve / local-only / abort).
7. On approve: dry-run optional, then `execute_split.py` with push+draft PRs (or local-only if requested). Add `--allow-optional-split` when the plan carries `threshold_note`; without it `execute_split.py` refuses before any git work.
8. After successful push+create with a draft URL for each entry in `planned_slice_count` (multi-slice only): supersede the source PR — comment merge order + child URLs via `--body-file`, then `gh pr close`. Skip when atomic, partial, local-only, or already superseded. Leave the source branch on the remote.
9. Report merge order, branch names, PR URLs, and supersede outcome (`closed` / `skipped`); leave source branch unchanged.
