"""Regex and capture-group indices for the same-file inline-duplicate message.

::

    suffix = "(inline duplicate body spans: helper at line 42 "
             "spanning 3 lines, enclosing at line 88 spanning 3 lines)"
    match = INLINE_DUPLICATE_BODY_VIOLATION_PATTERN.search(suffix)
    match.group(helper line index)     reads "42"  helper starts here
    match.group(helper span index)     reads "3"   helper runs this many lines
    match.group(enclosing line index)  reads "88"  enclosing copy starts here
    match.group(enclosing span index)  reads "3"   enclosing runs this many lines

The enforcer emits this suffix when a helper and its enclosing function share a
body. ``code_rules_gate`` parses the four fields to rebuild the union span the
commit/push gate scopes a deferred violation by.
"""

import re

INLINE_DUPLICATE_BODY_VIOLATION_PATTERN: re.Pattern[str] = re.compile(
    r"\(inline duplicate body spans: helper at line (\d+) spanning (\d+) lines, "
    r"enclosing at line (\d+) spanning (\d+) lines\)"
)
INLINE_DUPLICATE_BODY_HELPER_LINE_GROUP_INDEX: int = 1
INLINE_DUPLICATE_BODY_HELPER_SPAN_GROUP_INDEX: int = 2
INLINE_DUPLICATE_BODY_ENCLOSING_LINE_GROUP_INDEX: int = 3
INLINE_DUPLICATE_BODY_ENCLOSING_SPAN_GROUP_INDEX: int = 4
