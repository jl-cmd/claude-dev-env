"""Pattern and capture-group constants for the same-file inline-duplicate span.

The same-file inline-duplicate enforcer message names two functions that share a
body — the helper and the enclosing function carrying the inline copy — and the
live Write/Edit hook scopes the violation by the UNION of both spans. So the
message carries both spans, and ``code_rules_gate.inline_duplicate_body_span_lines``
parses them to reconstruct that union when the commit/push gate scopes a deferred
violation by added line. These constants describe the message suffix the enforcer
emits: ``(inline duplicate body spans: helper at line H spanning P lines,
enclosing at line E spanning Q lines)``.
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
