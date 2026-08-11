# audit-rubrics/prompts

Agent-ready audit prompt templates, one per category (A–Q). An agent inlines the artifact under review into the `[INLINE THE FULL ARTIFACT HERE]` placeholder and runs the prompt as-is.

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

## Prompt structure

Each template:
- Scopes the audit to one category only (skip the others)
- Lists all sub-buckets from the matching `category_rubrics/` file
- Requires each sub-bucket to produce at least one Shape A finding OR one Shape B proof-of-absence with three or more adversarial probes
- Uses `find` as the finding ID prefix (single-pass audits) rather than `loop<N>-<K>`

## Relationship to category_rubrics/

`prompts/` is the executable form; `category_rubrics/` is the reference form. When a sub-bucket decomposition changes in a rubric, update the matching prompt in the same commit.
