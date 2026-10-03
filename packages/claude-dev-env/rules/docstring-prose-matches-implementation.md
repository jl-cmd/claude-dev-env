---
paths:
  - "**/*.py"
  - "**/*.md"
---

# Docstring Prose Matches Implementation

**When this applies:** Writing or editing a docstring, or a skill's companion `SKILL.md`, whose prose lists the inputs, matches, skips, or step order a body applies.

The list covers every behavior the body applies, and the body accepts only what the list names. When the body changes the set, update the prose in the same edit. A hook's docstring and `CORRECTIVE_MESSAGE` claim exactly the shapes its detector flags.

**Enforcement:** `code_rules_docstrings.py` and the JS slices in `code_rules_imports_logging.py`, which the staged policy lint runs through `code_rules_enforcer.py`, plus its `hook-prose-consistency` rule. CI runs it against the merge base.

**Full text:** [`docs/rule-guides/docstring-prose-matches-implementation.md`](../docs/rule-guides/docstring-prose-matches-implementation.md), with the write-time checklist. The Category O audit rubric carries the full standard.
