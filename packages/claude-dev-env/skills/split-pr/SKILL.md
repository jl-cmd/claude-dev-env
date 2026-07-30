---
name: split-pr
description: >-
  Source-owned PR analyzer for the hand-written line metric and 200/600 split
  gates. Triggers: /split-pr analyze, split analysis, hand-written lines,
  200/600 PR split.
---

# split-pr (analyzer)

**Source-owned analyzer** for the locked hand-written line metric and the 200 /
600 split gates. Reports hand-written churn separately from excluded churn
(generated, vendor, minified, lockfile). File count informs judgment and is
never a hard gate.

## Gotchas

- **Hand-written lines are additions plus deletions** on non-excluded paths.
- **200 hand-written lines** require a recorded `split_analysis` document.
- **600 hand-written lines** default to multiple PR slices (`default_split`).
- **Atomic exception** at 600+ needs a recorded unsplittable reason and a
  standing Fable verdict token — never stay one PR silently.
- **File count is context only.** It never blocks analysis.

## When this applies

- User asks for a split analysis or hand-written line report on a PR or file list.
- A PR approaches or exceeds the 200 / 600 hand-written line surfaces.

## Process

1. Run `python scripts/analyze_pr.py --files-json <path> --pretty` (or `--pr N`).
2. Read `hand_written_lines`, `excluded_churn_lines`, `requires_split_analysis`,
   `default_split`, and optional `atomic_exception`.
3. At 200+ without a prior analysis artifact, record the analyzer JSON before
   shipping further commits on that surface.
4. At 600+ with `default_split=true`, plan multiple PR slices unless
   `atomic_exception` carries a Fable-approved reason.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Analyzer contract and 200/600 gates |
| `scripts/analyze_pr.py` | Emit analysis JSON from gh or offline files |
| `scripts/categorize_files.py` | Path churn class (hand-written vs excluded) |
| `scripts/split_pr_script_types.py` | Canonical split-plan build and path-assignment validation |
| `scripts/split_pr_title.py` | Collapse titles to exactly one conventional prefix |
| `scripts/split_pr_layer_order.py` | Deterministic config→other layer sort |
| `scripts/split_pr_paginate.py` | Paginated PR file intake via gh api --slurp |
| `scripts/pack_files_into_slices.py` | Pack annotated files into ≤200 hand-written-line slices by layer |
| `scripts/config/packing_constants.py` | Review budget, hard cap, path→layer markers for packing |
| `scripts/test_categorize_files_packing.py` | Budget packing and layer inference tests |
| `scripts/verify_plan.py` | Coverage verification: unique path assignment, path normalization, title contract |
| `scripts/test_verify_plan.py` | Full-coverage and gap rejection tests |
| `scripts/test_verify_plan_contract.py` | source_commit and title-normalization contract tests |
| `scripts/test_verify_plan_path_normalization.py` | Unsafe-path fail-closed tests |
| `scripts/split_pr_dependency_graph.py` | Deterministic layer-rank dependency graph over slices |
| `scripts/config/dependency_constants.py` | Graph key names and layer ranks |
| `scripts/test_split_pr_dependency_graph.py` | Graph order, duplicate-id, unknown-layer tests |
| `scripts/config/split_pr_constants.py` | Thresholds and excluded path markers |
| `scripts/config/plan_constants.py` | Plan schema keys, layer order, title-prefix tokens |
| `scripts/test_analyze_pr.py` | Boundary tests at 199/200/599/600 |
| `scripts/test_categorize_files.py` | Exclusion classification tests |
| `scripts/test_split_pr_script_types.py` | Plan schema and full path assignment |
| `scripts/test_split_pr_title.py` | One-prefix title normalization |
| `scripts/test_split_pr_layer_order.py` | Layer order ranking |
| `scripts/test_split_pr_paginate.py` | Slurp page flattening |
| `reference/proposal-format.md` | Human-readable plan field contract |

## Folder map

- `scripts/` — analyzer, categorize helpers, constants, tests
