"""Constants for the orphan-CSS-class check in code_rules_enforcer.

A Python module that builds HTML emits ``class="..."`` attributes in string
literals and pairs them with a ``<style>`` block whose selectors style those
classes. When a class appears in the markup but no selector defines it, the
markup carries a dead attribute or the style block is missing a rule. This
module holds the patterns that pair the two halves and the package-scan
budget that bounds the sibling read.
"""

import re

__all__ = [
    "CLASS_ATTRIBUTE_PATTERN",
    "STYLE_BLOCK_PATTERN",
    "CSS_CLASS_SELECTOR_PATTERN",
    "PYTHON_MODULE_GLOB",
    "MAX_ORPHAN_CSS_CLASS_ISSUES",
    "MAX_SIBLING_MODULES_SCANNED",
    "ORPHAN_CSS_CLASS_MESSAGE_SUFFIX",
]

CLASS_ATTRIBUTE_PATTERN: re.Pattern[str] = re.compile(r"""class\s*=\s*["']([^"']+)["']""")

STYLE_BLOCK_PATTERN: re.Pattern[str] = re.compile(
    r"<style[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE
)

CSS_CLASS_SELECTOR_PATTERN: re.Pattern[str] = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")

PYTHON_MODULE_GLOB: str = "*.py"

MAX_ORPHAN_CSS_CLASS_ISSUES: int = 10

MAX_SIBLING_MODULES_SCANNED: int = 60

ORPHAN_CSS_CLASS_MESSAGE_SUFFIX: str = (
    "add a matching '.<class>' selector to the <style> block, "
    "or drop the unused class attribute (CODE_RULES self-documenting markup)"
)
