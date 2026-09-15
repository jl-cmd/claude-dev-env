---
paths:
  - "**/*.workflow.js"
---

# Workflow Substitution Slot Rule

In a `.workflow.js` agent-prompt template, every per-call or per-iteration value an agent must fill in is marked with the angle-bracket convention — `<plate.svg>`, `<object.svg>`, `<glow_hex>`, `cand_<i>`. A bare token such as `cand_i` reads as a fixed literal, so an agent can create one literal directory named `cand_i` and overwrite it across every iteration of a loop, collapsing an N-iteration gate into a single run.

When a loop builds a per-iteration path or output key, write the index as a slot — `cand_<i>` — or spell out `replace <i> with the iteration index 0, 1, 2` in the step text. Every per-call value in a `.workflow.js` template carries angle brackets so an agent fills in a fresh value per call.

The staged policy lint carries this check as its `workflow-substitution` rule. It reports a `.workflow.js` file whose looped content holds a bare `<word>_<i|j|k>` token as a per-iteration path segment. Run `python packages/claude-dev-env/scripts/cde_lint.py --staged` before you commit. CI runs the same lint against the merge base. No write-time hook reports this, so a bare token stays on disk until the lint runs.
