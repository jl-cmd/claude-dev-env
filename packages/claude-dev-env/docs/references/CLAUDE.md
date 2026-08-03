# docs/references

Pointer documents to external sources, standard terminology, and internal tool or skill usage. Files here are loaded on demand by rules that cite them.

## Files

| File | Purpose |
|---|---|
| `dead-code-elimination.md` | External sources and standard terms behind CODE_RULES §9.8 (remove code you orphan): DCE, tree shaking, reachability analysis, and the Lava Flow anti-pattern |
| `code-review-enforcement.md` | How the code-review gates work: the two required efforts (push at low, PR creation at xhigh), the stamp bound to the branch-surface hash, the single sanctioned minter, the two-layer stamp-directory guard, and the bypass surfaces the gates leave open |
| `prose-style-enforcement.md` | How `CLAUDE_PROSE_STYLE_ENFORCEMENT` arms opinionated prose gates (default off) while AskUserQuestion lean-block stays always on |
| `advisor-tool.md` | Canonical consult bones for any stronger reviewer: when to call, hard rule before first write, how to treat advice; maps to the Anthropic advisor tool |
| `team-advisor-skill.md` | `/team-advisor` map: sole-consumer warm bind, ref index, and how it pairs with `advisor()` |
| `weak-executor-advisor.md` | Consult profile a below-advisor-tier executor (Sonnet, Haiku) follows on top of `advisor-tool.md`: spawn-prompt steering, context packaging, two-timing rule, consult budget, failure branches |

## Role

A file naming an external concept gives a one-line definition and links a direct source. A file naming an internal tool or skill describes what it does and when to use it. They back the rule text in `rules/` and `packages/claude-dev-env/docs/CODE_RULES.md` without embedding full third-party content inline.
