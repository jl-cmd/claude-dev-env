"""Audit PR body markdown for prose substance, shape, and structural rules.

Strips Markdown ceremony to measure substantive prose, classifies the body as
trivial, standard, or heavy, enumerates section headers, prepares the prose
scanned for vague language, and flags self-closing references to the PR's own
number and the discouraged "This PR ..." opening. Vague-language enforcement
runs in validate_pr_body in pr_description_enforcer.py.
"""

import re
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.pr_description_enforcer_constants import (  # noqa: E402
    BLOCKQUOTE_LINE_PATTERN,
    BLOCKQUOTE_MARKER_PATTERN,
    BOLD_PAIR_PATTERN,
    BULLET_MARKER_PATTERN,
    FENCED_CODE_BLOCK_PATTERN,
    HEADING_LINE_PATTERN,
    HEAVY_MIN_BODY_CHARS_FOR_CLASSIFICATION,
    HEAVY_SHAPE,
    INLINE_CODE_PATTERN,
    LINK_TEXT_PATTERN,
    SELF_REFERENCE_PATTERN_TEMPLATE,
    STANDARD_SHAPE,
    TABLE_ROW_LINE_PATTERN,
    THIS_PR_OPENING_PATTERN,
    TRIVIAL_BODY_CHAR_THRESHOLD,
    TRIVIAL_SHAPE,
    WHITESPACE_RUN_PATTERN,
)


def strip_markdown_ceremony(body: str) -> str:
    """Return the body with Markdown ceremony stripped to leave underlying prose.

    Removes fenced code, inline code, heading lines, blockquote markers,
    bullet list markers, bold/emphasis markers, and Markdown link targets.
    Whitespace is preserved so callers can collapse or measure it as needed.
    """
    body_without_fences = FENCED_CODE_BLOCK_PATTERN.sub("", body)
    body_without_inline_code = INLINE_CODE_PATTERN.sub("", body_without_fences)
    body_without_blockquotes = BLOCKQUOTE_MARKER_PATTERN.sub("", body_without_inline_code)
    body_without_headings = HEADING_LINE_PATTERN.sub("", body_without_blockquotes)
    body_without_bullets = BULLET_MARKER_PATTERN.sub("", body_without_headings)
    body_without_bold = BOLD_PAIR_PATTERN.sub(r"\1", body_without_bullets)
    body_without_emphasis = body_without_bold.replace("*", "")
    body_without_links = LINK_TEXT_PATTERN.sub(r"\1", body_without_emphasis)
    return body_without_links


def _count_substantive_prose_chars(body: str) -> int:
    """Return the count of prose characters after stripping Markdown ceremony.

    Collapses internal whitespace so a body of only headers and bullets --
    no real WHY paragraph -- registers as effectively empty.
    """
    stripped_body = strip_markdown_ceremony(body)
    body_collapsed = WHITESPACE_RUN_PATTERN.sub(" ", stripped_body).strip()
    return len(body_collapsed)


def _extract_vague_scan_text(body: str) -> str:
    """Return the prose to scan for vague language, with non-prose regions removed.

    Drops whole blockquote lines and whole pipe-delimited table rows, then strips
    the same Markdown ceremony as the prose-count path -- which removes fenced
    code, inline code, and whole heading lines. This exempts vague phrases that
    appear only inside code fences, inline code, Markdown headings, quoted
    reviewer text, or pipe-delimited example tables -- those are not the author's
    own prose. A pipe-delimited row carries at least two pipes; a line with a
    single leading pipe, or a borderless table row with no leading pipe, stays in
    scope.
    """
    without_blockquote_lines = BLOCKQUOTE_LINE_PATTERN.sub("", body)
    without_table_rows = TABLE_ROW_LINE_PATTERN.sub("", without_blockquote_lines)
    return strip_markdown_ceremony(without_table_rows)


def _iter_section_headers(body: str) -> list[str]:
    """Return every ATX heading line in the body, preserving canonical form.

    HEADING_LINE_PATTERN matches the leading hash run (one or more hash
    characters at line start), so the result spans every ATX level.
    Downstream callers in this module only test specific two-hash header
    strings, so matching every heading level keeps the parser permissive
    without changing behaviour for the canonical two-hash header shape.

    Fenced code blocks are stripped first so example markdown nested inside ``` fences
    (a PR body that demonstrates the Heavy shape, for instance) is not counted as a
    structural header. This keeps the shape classifier and Heavy required-header check
    aligned with `strip_markdown_ceremony`, which already strips fences before measuring.
    """
    body_without_fences = FENCED_CODE_BLOCK_PATTERN.sub("", body)
    all_headers: list[str] = []
    for each_match in HEADING_LINE_PATTERN.finditer(body_without_fences):
        header_text = each_match.group(0).strip()
        all_headers.append(header_text)
    return all_headers


def _compute_pr_body_shape(body: str) -> str:
    """Classify a PR body as `trivial`, `standard`, or `heavy` from content alone.

    Uses substantive prose chars (post-Markdown-strip) rather than raw length so the
    classifier and the ceremony-on-Trivial check both measure the same metric against
    TRIVIAL_BODY_CHAR_THRESHOLD; otherwise a body can be classified Standard by shape
    while simultaneously being flagged as Trivial-sized by the ceremony check.
    """
    substantive_length = _count_substantive_prose_chars(body)
    header_count = len(_iter_section_headers(body))

    if substantive_length < TRIVIAL_BODY_CHAR_THRESHOLD and header_count == 0:
        return TRIVIAL_SHAPE

    if substantive_length >= HEAVY_MIN_BODY_CHARS_FOR_CLASSIFICATION:
        return HEAVY_SHAPE

    return STANDARD_SHAPE


def _body_contains_any_header(body: str, all_candidate_headers: frozenset[str]) -> bool:
    body_headers_lower = {each_header.lower() for each_header in _iter_section_headers(body)}
    for each_candidate in all_candidate_headers:
        candidate_lower = each_candidate.lower()
        for each_present in body_headers_lower:
            if each_present == candidate_lower:
                return True
            if each_present.startswith(candidate_lower):
                character_after_candidate = each_present[len(candidate_lower)]
                if not (character_after_candidate.isalnum() or character_after_candidate == "_"):
                    return True
    return False


def _matches_self_closing_reference(body: str, pr_number: int) -> bool:
    pattern_source = SELF_REFERENCE_PATTERN_TEMPLATE.format(pr_number=pr_number)
    compiled_pattern = re.compile(pattern_source, re.IGNORECASE)
    return compiled_pattern.search(body) is not None


def _opens_with_this_pr_phrase(body: str) -> bool:
    return THIS_PR_OPENING_PATTERN.search(body) is not None
