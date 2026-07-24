# Split-further loop

Mandatory after Phase 5. Re-apply `/split-pr` to each new draft PR (or local slice) until nothing further is reasonably splittable. No `AskUserQuestion` on recursive passes — Pass 0 approval covers them.

## Constants

| Name | Value | Role |
|---|---|---|
| `MAXIMUM_RECURSIVE_SPLIT_DEPTH` | `3` | Generations below the original PR. Stop when depth would exceed this. |
| `MINIMUM_SPLIT_FILE_COUNT` | from `scripts/split_pr_scripts_constants/config/analyze_constants.py` | Advisory context only (`threshold_note` / warnings). **Never a stop gate.** |

## Queue

1. Seed BFS queue with every draft PR (or local branch) Phase 4 created. Depth of each seed = `1`.
2. While the queue is non-empty, dequeue one candidate.
3. If `depth > MAXIMUM_RECURSIVE_SPLIT_DEPTH` → stop that candidate; log `stop:depth_cap`.
4. Run Phase 1–2 on that PR (`analyze_pr` → refine → **`verify_plan` must pass**). Skip Phase 3.
5. **Primary stop** — `proposed_slices` has fewer than 2 non-empty slices → log `stop:lt2_slices`; do not execute.
6. **Secondary stop** — agent judges no independent review story (only trivial re-bucket) → log `stop:judgment:<reason>`; do not execute.
7. Otherwise execute with the **same mode as Pass 0** (push+draft PRs or local-only). Each child source branch stays intact.
8. Enqueue every new child at `depth + 1`.
9. When the queue drains, report all leaves, stop reasons, and the full stack merge order.

## Rules

- Coverage verify on every recursive pass (same as Pass 0). Never skip `verify_plan.py`.
- Draft only. No force-push. No `gh pr ready`.
- Single-layer or small file counts may still split when analyze yields ≥2 non-empty slices.
- Abort recursive work on execute failure for that candidate; keep siblings already landed; report partial stack.
