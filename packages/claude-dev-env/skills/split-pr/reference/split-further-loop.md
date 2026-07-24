# Split-further loop

Mandatory after Phase 5. Re-apply `/split-pr` to each new draft PR (or local slice) until every leaf **fits a small review** or is a recorded atomic exception. No `AskUserQuestion` on recursive passes — Pass 0 approval covers them.

## Constants

| Name | Value | Role |
|---|---|---|
| `MAXIMUM_RECURSIVE_SPLIT_DEPTH` | `3` | Generations below the original PR. Stop when depth would exceed this. |
| `MAXIMUM_SLICE_CHANGED_LINES` | `400` | Hard review-line budget per slice (additions + deletions). |
| `MAXIMUM_SLICE_FILE_COUNT` | `10` | Hard file-count budget per slice. |
| `MINIMUM_SPLIT_FILE_COUNT` | from `analyze_constants.py` | Advisory only when the parent does **not** already fit review size. Never a Phase-6 stop. |

A slice **fits a small review** when `slice_fits_review_budget` is true (both maximums hold). See `splitting-principles.md`.

## Queue

1. Seed BFS queue with every draft PR (or local branch) Phase 4 created. Depth of each seed = `1`.
2. While the queue is non-empty, dequeue one candidate.
3. If `depth > MAXIMUM_RECURSIVE_SPLIT_DEPTH` → stop that candidate; log `stop:depth_cap`.
4. Run Phase 1–2 on that PR (`analyze_pr` → refine → **`verify_plan` must pass**). Skip Phase 3.
5. **Primary stop — already review-sized** — the candidate as a whole passes `slice_fits_review_budget`, **or** every proposed non-empty slice has `fits_review: true` and packing produced a single non-empty slice → log `stop:fits_review`; do not execute.
6. **Primary stop — no further multi-slice plan** — `proposed_slices` has fewer than 2 non-empty slices **and** the single slice is either review-sized or `oversized_atomic` → log `stop:lt2_slices` or `stop:oversized_atomic`; do not execute.
7. **Continue when oversized** — if packing / re-analyze yields **≥2** non-empty slices (layer pack or path-prefix pack), execute even when the candidate is a single path-layer. That is the path that fixes large `other` leaves.
8. **Secondary stop** — agent judges no independent review story (only trivial re-bucket that does not reduce size) → log `stop:judgment:<reason>`; do not execute.
9. Otherwise execute with the **same mode as Pass 0** (push+draft PRs or local-only). Each child source branch stays intact.
10. Enqueue every new child at `depth + 1`.
11. When the queue drains, report all leaves, stop reasons, and the full stack merge order.

## Rules

- Coverage **and** review-budget verify on every recursive pass (`verify_plan`). Never skip `verify_plan.py`.
- Draft only. No force-push. No `gh pr ready`.
- Single-layer leaves still split when packing yields ≥2 budget-fitting parts.
- Abort recursive work on execute failure for that candidate; keep siblings already landed; report partial stack.
