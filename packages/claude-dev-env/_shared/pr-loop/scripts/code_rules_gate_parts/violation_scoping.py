"""Partition enforcer violations into blocking versus advisory by touched line.

Every diff-scoped enforcer message carries the line span of the unit it flags.
These extractors recover that span from the message text, and
``split_violations_by_scope`` marks a violation blocking when its span meets a
line the current diff added, advisory otherwise.
"""

import re
from collections.abc import Callable

from pr_loop_shared_constants.code_rules_gate_constants import (
    BANNED_NOUN_DEFINITION_LINE_GROUP_INDEX,
    BANNED_NOUN_SPAN_GROUP_INDEX,
    BANNED_NOUN_VIOLATION_PATTERN,
    DUPLICATE_BODY_DEFINITION_LINE_GROUP_INDEX,
    DUPLICATE_BODY_SPAN_GROUP_INDEX,
    DUPLICATE_BODY_VIOLATION_PATTERN,
    FUNCTION_LENGTH_DEFINITION_LINE_GROUP_INDEX,
    FUNCTION_LENGTH_SPAN_GROUP_INDEX,
    FUNCTION_LENGTH_VIOLATION_PATTERN,
    ISOLATION_DEFINITION_LINE_GROUP_INDEX,
    ISOLATION_SPAN_GROUP_INDEX,
    ISOLATION_VIOLATION_PATTERN,
)
from pr_loop_shared_constants.inline_duplicate_body_span_constants import (
    INLINE_DUPLICATE_BODY_ENCLOSING_LINE_GROUP_INDEX,
    INLINE_DUPLICATE_BODY_ENCLOSING_SPAN_GROUP_INDEX,
    INLINE_DUPLICATE_BODY_HELPER_LINE_GROUP_INDEX,
    INLINE_DUPLICATE_BODY_HELPER_SPAN_GROUP_INDEX,
    INLINE_DUPLICATE_BODY_VIOLATION_PATTERN,
)


def _span_lines(span_match: re.Match[str], line_group_index: int, span_group_index: int) -> range:
    """Build the line range from a match's start-line and span capture groups.

    Args:
        span_match: A regex match carrying a start line and a span length.
        line_group_index: The capture-group index of the start line.
        span_group_index: The capture-group index of the span length.

    Returns:
        The range covering the declared span.
    """
    start_line = int(span_match.group(line_group_index))
    line_span = int(span_match.group(span_group_index))
    return range(start_line, start_line + line_span)


def hunk_header_pattern() -> re.Pattern[str]:
    """Return the regex matching a unified-diff hunk header.

    Returns:
        A pattern capturing the new-side start line and optional count.
    """
    return re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def violation_line_pattern() -> re.Pattern[str]:
    """Return the regex matching a violation's ``Line N:`` prefix.

    Returns:
        A pattern capturing the line number named in the prefix.
    """
    return re.compile(r"^Line (\d+):")


def parse_added_line_numbers(unified_diff_text: str) -> set[int]:
    """Extract added line numbers from unified-diff text.

    Args:
        unified_diff_text: Output from ``git diff --unified=0``.

    Returns:
        The set of newly-added line numbers named by the hunk headers.
    """
    header_regex = hunk_header_pattern()
    added_line_numbers: set[int] = set()
    for each_line in unified_diff_text.splitlines():
        header_match = header_regex.match(each_line)
        if header_match is None:
            continue
        new_start_text, new_count_text = header_match.groups()
        new_start = int(new_start_text)
        new_count = 1 if new_count_text is None else int(new_count_text)
        if new_count <= 0:
            continue
        added_line_numbers.update(range(new_start, new_start + new_count))
    return added_line_numbers


def extract_violation_line_number(violation_text: str) -> int | None:
    """Return the line number captured by the violation-line prefix regex.

    Args:
        violation_text: A single violation string of the form ``Line N: ...``.

    Returns:
        The integer line number in the prefix, or None when it does not match.
    """
    prefix_match = violation_line_pattern().match(violation_text)
    if prefix_match is None:
        return None
    return int(prefix_match.group(1))


def function_length_span_range(violation_text: str) -> range | None:
    """Return the declared line span of a function-length violation, or None.

    ::

        message: Function 'f' (defined at line X) is Y lines - ...
        ok:   a function-length message -> range covering the function
        flag: another message           -> None

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        A range over the function's declared span, or None for another message.
    """
    span_match = FUNCTION_LENGTH_VIOLATION_PATTERN.search(violation_text)
    if span_match is None:
        return None
    return _span_lines(
        span_match,
        FUNCTION_LENGTH_DEFINITION_LINE_GROUP_INDEX,
        FUNCTION_LENGTH_SPAN_GROUP_INDEX,
    )


def isolation_span_range(violation_text: str) -> range | None:
    """Return the enclosing test-function span of an isolation violation, or None.

    ::

        message: Line N: Test 'f' (defined at line X, spanning Y lines) probes ...
        ok:   an isolation message -> range covering the test function
        flag: another message      -> None

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        A range over the enclosing test span, or None for another message.
    """
    span_match = ISOLATION_VIOLATION_PATTERN.search(violation_text)
    if span_match is None:
        return None
    return _span_lines(
        span_match,
        ISOLATION_DEFINITION_LINE_GROUP_INDEX,
        ISOLATION_SPAN_GROUP_INDEX,
    )


def banned_noun_span_range(violation_text: str) -> range | None:
    """Return the one-line binding span of a banned-noun violation, or None.

    ::

        message: Line N: Identifier 'x' ... (binding span at line X, spanning 1 lines)
        ok:   a banned-noun message -> range covering the binding line
        flag: another message       -> None

    The span is the binding line alone, so a pre-existing binding stays out of
    scope when an unrelated line of its enclosing function is edited.

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        A range over the binding's one-line span, or None for another message.
    """
    span_match = BANNED_NOUN_VIOLATION_PATTERN.search(violation_text)
    if span_match is None:
        return None
    return _span_lines(
        span_match,
        BANNED_NOUN_DEFINITION_LINE_GROUP_INDEX,
        BANNED_NOUN_SPAN_GROUP_INDEX,
    )


def duplicate_body_span_range(violation_text: str) -> range | None:
    """Return the copied function's source line span of a duplicate-body issue.

    ::

        message: Function 'f' duplicates a.py::f — (duplicate body span at line X ...)
        ok:   a duplicate-body message -> range covering the copy
        flag: another message          -> None

    A duplicate blocks only when the diff touches the copied function; an
    unrelated edit that leaves a pre-existing copy alone keeps it advisory.

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        A range over the copied function's span, or None for another message.
    """
    span_match = DUPLICATE_BODY_VIOLATION_PATTERN.search(violation_text)
    if span_match is None:
        return None
    return _span_lines(
        span_match,
        DUPLICATE_BODY_DEFINITION_LINE_GROUP_INDEX,
        DUPLICATE_BODY_SPAN_GROUP_INDEX,
    )


def inline_duplicate_body_span_lines(violation_text: str) -> frozenset[int] | None:
    """Return the union of both spans of a same-file inline-duplicate issue.

    ::

        message: ... helper at line H spanning P, enclosing at line E spanning Q
        ok:   an inline-duplicate message -> frozenset of both spans
        flag: another message             -> None

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        The frozenset of every line in both spans, or None for another message.
    """
    span_match = INLINE_DUPLICATE_BODY_VIOLATION_PATTERN.search(violation_text)
    if span_match is None:
        return None
    helper_lines = _span_lines(
        span_match,
        INLINE_DUPLICATE_BODY_HELPER_LINE_GROUP_INDEX,
        INLINE_DUPLICATE_BODY_HELPER_SPAN_GROUP_INDEX,
    )
    enclosing_lines = _span_lines(
        span_match,
        INLINE_DUPLICATE_BODY_ENCLOSING_LINE_GROUP_INDEX,
        INLINE_DUPLICATE_BODY_ENCLOSING_SPAN_GROUP_INDEX,
    )
    return frozenset(helper_lines) | frozenset(enclosing_lines)


def _all_span_range_extractors() -> tuple[Callable[[str], range | None], ...]:
    """Return every enclosing-unit span extractor, tried in order."""
    return (
        function_length_span_range,
        isolation_span_range,
        banned_noun_span_range,
        duplicate_body_span_range,
    )


def enclosing_span_range(violation_text: str) -> range | None:
    """Return the enclosing-unit span of a span-tagged violation, or None.

    ::

        each extractor in the registry is tried in turn
        ok:   a span-tagged message -> the first range an extractor recovers
        flag: an untagged message   -> None

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        The first non-None span any extractor recovers, or None.
    """
    for each_extractor in _all_span_range_extractors():
        span_range = each_extractor(violation_text)
        if span_range is not None:
            return span_range
    return None


def _issue_is_blocking(each_issue: str, all_added_line_numbers: set[int]) -> bool:
    """Return True when *each_issue* is blocking for the given added lines.

    Args:
        each_issue: A single violation string emitted by the enforcer.
        all_added_line_numbers: Lines the current diff added.

    Returns:
        True when the issue's span or line meets an added line.
    """
    inline_duplicate_lines = inline_duplicate_body_span_lines(each_issue)
    if inline_duplicate_lines is not None:
        return bool(inline_duplicate_lines & all_added_line_numbers)
    span_range = enclosing_span_range(each_issue)
    if span_range is not None:
        return any(each_line in all_added_line_numbers for each_line in span_range)
    violation_line = extract_violation_line_number(each_issue)
    if violation_line is None:
        return True
    return violation_line in all_added_line_numbers


def split_violations_by_scope(
    all_issues: list[str],
    all_added_line_numbers: set[int] | None,
) -> tuple[list[str], list[str]]:
    """Partition issues into blocking versus advisory based on touched lines.

    ::

        all_added_line_numbers is None -> every issue is blocking
        an issue whose span meets an added line -> blocking
        an issue on a pre-existing untouched unit -> advisory

    Args:
        all_issues: Violation strings emitted by the enforcer.
        all_added_line_numbers: Lines added in the current diff, or None to
            treat every violation as blocking.

    Returns:
        The tuple ``(blocking, advisory)``.
    """
    if all_added_line_numbers is None:
        return list(all_issues), []
    blocking: list[str] = []
    advisory: list[str] = []
    for each_issue in all_issues:
        if _issue_is_blocking(each_issue, all_added_line_numbers):
            blocking.append(each_issue)
        else:
            advisory.append(each_issue)
    return blocking, advisory
