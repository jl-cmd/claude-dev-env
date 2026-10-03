---
paths:
  - "**/*.py"
---

# Plain, Illustrative Docstrings

**When this applies:** Writing or editing the narrative prose of a public function, method, class, or module docstring, the text before its first `Args:` section.

Write the narrative so a general developer follows it on the first read. Paint a concrete scene in short sentences, one idea each. Name what the reader sees and why it matters. Say what a thing is. Once the explanation grows past two or three lines, use one summary line, then a `::` literal block or a doctest that shows the input and the outcome, then two or three short lines, then the Google `Args:` and `Returns:` sections.

**Enforcement:** `check_docstring_runon_sentence` and `check_docstring_prose_wall_without_illustration` in `code_rules_docstrings.py`, which the staged policy lint runs through `code_rules_enforcer.py`. Category O sub-bucket O9 of the audit rubric carries the judgment.

**Full text:** [`docs/rule-guides/plain-illustrative-docstrings.md`](../docs/rule-guides/plain-illustrative-docstrings.md), with the canonical example.
