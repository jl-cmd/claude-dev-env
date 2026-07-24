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

**Precedence:** when the **parent PR as a whole** already fits both budgets, treat the parent as already review-sized (`fits_review` / threshold note). That check supersedes `MINIMUM_SPLIT_FILE_COUNT` as an initiation stop; the minimum remains advisory-only in the proposal.

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
