---
paths:
  - "**/*.py"
---

# Orphan CSS Class in Generated Markup

**When this applies:** Production `.py` that emits `class="..."` attributes in string literals beside a `<style>` block.

Every class the markup references has a `.<class>` selector in a nearby `<style>` block. Add the selector in the change that adds the class, and drop the class in the change that drops its selector.

**Enforcement:** `check_orphan_css_classes` in `code_rules_orphan_css_class.py`, which the staged policy lint runs through `code_rules_enforcer.py`.

**Full text:** [`docs/rule-guides/orphan-css-class.md`](../docs/rule-guides/orphan-css-class.md).
