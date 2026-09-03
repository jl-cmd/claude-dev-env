"""Extract JavaScript comments without matching comment-like strings."""

import io
import re
import tokenize
from typing import NamedTuple

from hooks_constants.code_rules_enforcer_constants import (
    ALL_JAVASCRIPT_EXEMPT_COMMENT_PREFIXES,
    ALL_JAVASCRIPT_EXEMPT_INLINE_COMMENT_PREFIXES,
    ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS,
)


class JavaScriptCommentOccurrence(NamedTuple):
    """One JavaScript comment with its source line and placement."""

    text: str
    line_number: int
    is_inline: bool


def _mask_javascript_strings(content: str) -> str:
    """Replace quoted JavaScript strings while preserving source positions."""
    string_pattern = r'''("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)'''
    return re.sub(
        string_pattern,
        lambda each_match: "".join(
            "\n" if each_character == "\n" else " "
            for each_character in each_match.group()
        ),
        content,
        flags=re.DOTALL,
    )


def _is_allowed_comment(
    comment_text: str, is_inline: bool, include_directive_comments: bool
) -> bool:
    """Return whether a comment is excluded from the policy comparison."""
    if comment_text.startswith("/**"):
        return True
    if include_directive_comments:
        return False
    prefixes = (
        ALL_JAVASCRIPT_EXEMPT_INLINE_COMMENT_PREFIXES
        if is_inline
        else ALL_JAVASCRIPT_EXEMPT_COMMENT_PREFIXES
    )
    comment_body = (
        comment_text.removeprefix("//").lstrip()
        if comment_text.startswith("//")
        else comment_text
    )
    return comment_body.startswith(prefixes)


def extract_javascript_comment_occurrences(
    content: str, include_directive_comments: bool
) -> list[JavaScriptCommentOccurrence]:
    """Return real JavaScript comment occurrences with exact line numbers."""
    masked_content = _mask_javascript_strings(content)
    all_occurrences: list[JavaScriptCommentOccurrence] = []
    for each_match in re.finditer(r"//[^\n]*|/\*[\s\S]*?\*/", masked_content):
        comment_text = content[each_match.start() : each_match.end()].strip()
        line_start = masked_content.rfind("\n", 0, each_match.start()) + 1
        is_inline = bool(masked_content[line_start : each_match.start()].strip())
        if _is_allowed_comment(comment_text, is_inline, include_directive_comments):
            continue
        line_number = content.count("\n", 0, each_match.start()) + 1
        all_occurrences.append(
            JavaScriptCommentOccurrence(comment_text, line_number, is_inline)
        )
    return all_occurrences


def extract_python_comment_occurrences(
    content: str,
) -> tuple[list[JavaScriptCommentOccurrence], bool]:
    """Return Python comments with exact lines and a tokenize status."""
    source_lines = content.split("\n")
    try:
        all_tokens = list(tokenize.generate_tokens(io.StringIO(content).readline))
    except ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS:
        return [], False
    all_occurrences: list[JavaScriptCommentOccurrence] = []
    for each_token in all_tokens:
        if each_token.type != tokenize.COMMENT:
            continue
        if each_token.string.startswith("#!") and each_token.start == (1, 0):
            continue
        source_line = source_lines[each_token.start[0] - 1]
        is_inline = bool(source_line[: each_token.start[1]].strip())
        all_occurrences.append(
            JavaScriptCommentOccurrence(
                each_token.string.strip(), each_token.start[0], is_inline
            )
        )
    return all_occurrences, True
