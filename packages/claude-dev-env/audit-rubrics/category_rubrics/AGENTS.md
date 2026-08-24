# audit-rubrics/category_rubrics

One rubric file per audit category (A–Q). Each file defines what the category covers, gives concrete examples of findings, and provides the sub-bucket decomposition an audit agent uses to structure its pass.

## Files

| File | Category |
|---|---|
| `category-a-api-contracts.md` | A — API contract verification |
| `category-b-selector-engine-compat.md` | B — Selector engine compatibility |
| `category-c-resource-cleanup.md` | C — Resource cleanup |
| `category-d-scoping-and-ordering.md` | D — Scoping and ordering |
| `category-e-dead-code.md` | E — Dead code |
| `category-f-silent-failures.md` | F — Silent failures |
| `category-g-bounds-and-overflow.md` | G — Bounds and overflow |
| `category-h-security-boundaries.md` | H — Security boundaries |
| `category-i-concurrency.md` | I — Concurrency |
| `category-j-code-rules-compliance.md` | J — Code-rules compliance |
| `category-k-codebase-conflicts.md` | K — Codebase conflicts |
| `category-l-behavior-equivalence.md` | L — Behavior equivalence |
| `category-m-producer-consumer-cardinality.md` | M — Producer-consumer cardinality |
| `category-n-test-name-scenario-verifier.md` | N — Test name / scenario verifier |
| `category-o-docstring-vs-impl-drift.md` | O — Docstring vs implementation drift |
| `category-p-name-vs-behavior-contract.md` | P — Name vs behavior contract |
| `category-q-cross-surface-claims.md` | Q — Cross-surface claim consistency |

## Rubric structure

Each file has:
- A plain-language description of what the category audits
- Concrete finding examples
- A companion-reference pointer to `../source-material-section-types.md`
- A sub-bucket decomposition table with stable IDs (A1, A2, …) and the concrete checks each bucket requires

## Relationship to prompts/

`category_rubrics/` is the human-readable reference. `prompts/` holds the agent-ready prompt templates that inline the same sub-bucket list in a structured prompt format. Keep both in sync when sub-buckets change.
