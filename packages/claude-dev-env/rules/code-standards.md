---
paths:
  - "**/*.py"
  - "**/*.mjs"
  - "**/*.js"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.ps1"
---

# Code Standards

[`CODE_RULES.md`](../docs/CODE_RULES.md) is the review contract for code quality. Load it when you review a pull request, resolve a policy conflict, or generate code. Red, green, refactor is the default loop (CODE_RULES §8). Keep engineering right-sized (CODE_RULES §7).

**Enforcement:** the staged policy lint runs `hooks/blocking/code_rules_enforcer.py` over each changed file, and CI runs it against the merge base.

**Full text:** [`docs/rule-guides/code-standards.md`](../docs/rule-guides/code-standards.md), with the policy surface map.
