# Split-further loop

Opt-in after Phase 5, default OFF: this loop runs only when the operator passes `--split-further`. When it runs, it walks each new draft PR (or local slice) and reports whether that leaf **fits a small review**, is a recorded atomic exception, or is still oversized. Every non-dry-run execute needs its own approval: Pass 0's approval covers Pass 0 alone, so any further split asks again with a fresh `AskUserQuestion`.

The loop never executes a second generation. Pass 0 creates one generation of children below the original PR, and nothing re-splits those children.

## Constants

| Name | Value | Role |
|---|---|---|
| `MAXIMUM_EXECUTABLE_SPLIT_DEPTH` | `0` (from `execute_constants.py`) | Highest split depth a run may execute at. Pass 0 is depth 0. A plan whose source branch is a generated `split/<pr>/<NN>-<slug>` branch reads as depth 1 and stops. |
| `GENERATED_SLICE_BRANCH_DEPTH` | `1` (from `execute_constants.py`) | Depth reported for a source branch the split pipeline generated. |
| `MAXIMUM_SLICE_CHANGED_LINES` | `400` | Hard review-line budget per slice (additions + deletions). |
| `MAXIMUM_SLICE_FILE_COUNT` | `10` | Hard file-count budget per slice. |
| `MINIMUM_SPLIT_FILE_COUNT` | from `analyze_constants.py` | Advisory only when the parent does **not** already fit review size. Never a Phase-6 stop. |

A slice **fits a small review** when `slice_fits_review_budget` is true (both maximums hold). See `splitting-principles.md`.

## How the depth bound holds

`execute_split.py` reads the depth from the plan itself, through `derive_split_depth_from_source_branch`. A source branch under the `split/` prefix is output of an earlier split pass, so it reads as depth 1 and the run stops before any branch, push, or PR. `--recursion-depth` may raise that depth, never lower it, so a caller that leaves the flag off still gets the stop.

## Queue (report only)

1. Seed a BFS queue with every draft PR (or local branch) Phase 4 created. Depth of each seed is `1`.
2. While the queue is non-empty, dequeue one candidate.
3. Every seed sits above `MAXIMUM_EXECUTABLE_SPLIT_DEPTH`, so log `stop:depth_cap` for it and execute nothing. The queue drains after one round.
4. Optionally run Phase 1–2 on the candidate (`analyze_pr` → refine → `verify_plan`) to record the slice table that a further split would produce. Report it; do not execute it.
5. Record the review-size finding for the leaf: `fits_review`, `lt2_slices`, `oversized_atomic`, or still oversized with the proposed slice count.
6. When the queue drains, report every leaf, its stop reason, its review-size finding, and the full stack merge order.

## Splitting a slice further

A slice that is still too large stays a manual decision. Run `/split-pr` on that slice PR only after a fresh operator approval, and expect `execute_split.py` to refuse it while the source branch carries the generated `split/…` name — the refusal is the runaway guard, not a bug. Cut the extra slices by hand, or re-cut the original PR with a different plan.

## Rules

- Coverage **and** review-budget verify on every analysis pass (`verify_plan`). Never skip `verify_plan.py`.
- Draft only. No force-push. No `gh pr ready`.
- Report a candidate the analysis pass fails; keep siblings already landed.
