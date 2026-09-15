---
paths:
  - "**/*.py"
---

# Orphan CSS Class in Generated Markup

**When this applies:** Any Write or Edit to a production `.py` file that builds HTML by emitting `class="..."` attributes inside string literals and pairs them with a `<style>` block — in the same file or in a companion module beside it.

## Rule

Every class name a markup string references has a matching `.<class>` selector in the `<style>` block. A class that appears in the markup but carries no selector anywhere is a dead attribute (or a missing rule): the markup names a style that the stylesheet never defines, so a reader who trusts the class to be styled is misled, and the attribute adds noise without effect.

When you add a `class="..."` attribute, add its `.<class>` selector to the `<style>` block in the same change. When you drop a selector, drop the class attribute it styled.

## What the check covers

The `check_orphan_css_classes` check in `code_rules_orphan_css_class.py` reaches production Python through the staged policy lint, whose `code-rules` rule loads `code_rules_enforcer.py` and applies it to each changed file. Run `python packages/claude-dev-env/scripts/cde_lint.py --staged` before you commit. CI runs the same lint against the merge base. It:

1. Collects each class name referenced in a `class="..."` attribute across the file's string literals.
2. Collects each class selector defined in a `<style>` block — both in the file under edit and in every Python module beside it (its own directory and immediate child directories), since a markup module commonly imports its style constant from a companion package directory.
3. Flags each referenced class with no matching selector in that whole set.

The check stays quiet for a file that emits no `class="..."` markup, and for a file whose markup has no `<style>` source nearby (its stylesheet lives outside the scan, so the check cannot judge it). Test files are exempt, since a fixture may carry intentional orphan markup.

## Why this check is mechanical

A class attribute with no matching selector reads as styled but renders unstyled. Native elements such as `<details>` stay functional without CSS, so the gap survives review as a cosmetic defect rather than a crash. That is the class of issue a manual pass slips past, and it lands later as a deferred code-standard finding. Running the lint on every staged change keeps the markup and the stylesheet in step.
