# docs/references

Pointer documents to external sources and standard terminology. Files here are loaded on demand by rules that cite external resources.

## Files

| File | Purpose |
|---|---|
| `dead-code-elimination.md` | External sources and standard terms behind CODE_RULES §9.8 (remove code you orphan): DCE, tree shaking, reachability analysis, and the Lava Flow anti-pattern |
| `code-review-enforcement.md` | How the code-review gates work: the two required efforts (push at low, PR creation at xhigh), the stamp bound to the branch-surface hash, the single sanctioned minter, the two-layer stamp-directory guard, and the bypass surfaces the gates leave open |

## Role

Each file names an external concept, gives a one-line definition, and links a direct source. They back the rule text in `rules/` and `packages/claude-dev-env/docs/CODE_RULES.md` without embedding full third-party content inline.
