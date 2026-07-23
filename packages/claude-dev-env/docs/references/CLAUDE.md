# docs/references

Pointer documents to external sources, standard terminology, and internal tool or skill usage. Files here are loaded on demand by rules that cite them.

## Files

| File | Purpose |
|---|---|
| `dead-code-elimination.md` | External sources and standard terms behind CODE_RULES §9.8 (remove code you orphan): DCE, tree shaking, reachability analysis, and the Lava Flow anti-pattern |
| `code-review-enforcement.md` | How the code-review gates work: the two required efforts (push at low, PR creation at xhigh), the stamp bound to the branch-surface hash, the single sanctioned minter, the two-layer stamp-directory guard, and the bypass surfaces the gates leave open |
| `advisor-tool.md` | The `advisor()` tool: a no-parameter review call that forwards the full conversation history to a stronger reviewer model, and when to call it |
| `team-advisor-skill.md` | The `/team-advisor` skill: spawning a standing review agent at the strongest reachable tier, and how it relates to the `advisor()` tool |

## Role

A file naming an external concept gives a one-line definition and links a direct source. A file naming an internal tool or skill describes what it does and when to use it. They back the rule text in `rules/` and `packages/claude-dev-env/docs/CODE_RULES.md` without embedding full third-party content inline.
