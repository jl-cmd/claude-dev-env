# File-based PR splitting principles

Load when heuristics need a re-rank or the user challenges slice order.

## Goal

Each PR tells **one story** a human can review without holding the whole feature in working memory. Slices form a **dependency chain**: later PRs base on earlier ones.

## Fits a small review

Every published slice must **fit a small review** so defect detection stays high:

| Budget | Constant | Default |
|---|---|---|
| Changed lines (additions + deletions) | `MAXIMUM_SLICE_CHANGED_LINES` | `400` |
| File count | `MAXIMUM_SLICE_FILE_COUNT` | `10` |

A slice fits when **both** budgets hold (`slice_fits_review_budget`).  
`analyze_pr` / `categorize_files` pack each path-layer under these budgets (directory groups, then file packing).  
`verify_plan` **fails** a multi-file slice that still exceeds the budget.  
A **single file** over the line budget is `oversized_atomic` — terminal; do not invent intra-file splits.

## The initiation stop

The same two budgets decide whether a split starts at all. `analyze_pr` measures the **parent PR as a whole** with `slice_fits_review_budget(file_count=…, changed_lines=…)`. When the parent fits both budgets it is already review-sized, and the plan says so in two places:

- `threshold_note` carries the text `parent already fits review budget (files=<n>/10, changed_lines=<n>/400); split is optional — continue only if the user insists`.
- `warnings` carries `parent_fits_review_budget_split_optional`.
- `proposed_slices` holds **one** slice built by `build_whole_pr_slice`: `index` 1, `slug` `whole-pr`, `layer` `other`, `title` `<prefix>: <feature-slug> single reviewable slice`, and every changed path in its `files` list.

`execute_split` calls `assert_split_is_advised(plan_payload, should_allow_optional_split)` before it touches git. A truthy `threshold_note` with no override raises:

```
plan says the split is optional (<threshold_note>); pass --allow-optional-split to execute it anyway
```

Recovery: leave the PR whole, or re-run `execute_split.py` with `--allow-optional-split` when the user insists on the one-slice `whole-pr` chain.

## Default chain

1. **Database** — schema, migrations  
2. **Contracts** — shared types, protos  
3. **Backend** — API, services, middleware  
4. **Frontend** — UI, hooks, pages  
5. **Tests** — unit/integration coverage  
6. **Config** — packaging, CI, lockfiles  
7. **Docs** — markdown / docs tree  

Skip empty layers. Keep tests with their layer only when the user wants vertical slices; default is a dedicated tests slice so production code reviews stay focused.

## Independence rules

- Slice N must build on merge of 1…N−1 (stacked bases).
- Prefer each slice green on its own after prior merges (project-specific validate is judgment; this skill does not invent `npm test` for every repo).
- Never leave a source path unassigned.

## What this skill does not do

- Line-level hunk splitting (`git add -p`)  
- Interactive “write me a bash script” tutoring  
- Review or converge of the resulting PRs (hand off to `/pr-converge`)
