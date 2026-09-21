"""Find contrast framing in authored prose.

A contrast defines its subject against a rejected alternative, so the reader
carries two readings where one would do.

::

    all_hits = find_contrast_framing("A diff regression, not shared code.")
    ok:   all_hits == [(1, 18, "trailing-comma-not")]
    flag: find_contrast_framing("The function runs more than 30 lines.") == []

Code spans, fenced blocks, paths, and link targets are blanked before the
patterns run, so an example quoted in backticks stays quiet. The pattern list
lives in the constants module beside this one, and the durable post linter
reads the same list.
"""

from __future__ import annotations

from banned_prose_words import prose_lines
from dev_env_scripts_constants.contrast_framing_constants import (
    ALL_CONTRAST_FRAMING_FORMS,
    CONTRAST_FRAMING_MESSAGE_TEMPLATE,
    CONTRAST_FRAMING_QUOTED_LINE_LIMIT,
    ContrastFramingForm,
)


def _line_hits(line_number: int, prose_line: str) -> list[tuple[int, int, str]]:
    return [
        (line_number, each_match.start() + 1, each_form.name)
        for each_form in ALL_CONTRAST_FRAMING_FORMS
        for each_match in each_form.pattern.finditer(prose_line)
    ]


def find_contrast_framing(document_text: str) -> list[tuple[int, int, str]]:
    """Return each contrast-framing occurrence in authored prose.

    Args:
        document_text: Full document source.

    Returns:
        Ordered ``(line number, column, form name)`` triples, both 1-based.
    """
    all_hits: list[tuple[int, int, str]] = []
    for each_line_number, each_prose_line in enumerate(prose_lines(document_text), 1):
        all_hits.extend(_line_hits(each_line_number, each_prose_line))
    return sorted(all_hits)


def form_named(form_name: str) -> ContrastFramingForm:
    """Return the contrast form carrying one name.

    Args:
        form_name: Name reported by ``find_contrast_framing``.

    Returns:
        The matching form.

    Raises:
        KeyError: If no form carries that name.
    """
    for each_form in ALL_CONTRAST_FRAMING_FORMS:
        if each_form.name == form_name:
            return each_form
    raise KeyError(form_name)


def describe_contrast_framing(
    document_text: str, line_number: int, form_name: str
) -> str:
    """Return the reader-facing message for one occurrence.

    Args:
        document_text: Full document source.
        line_number: 1-based line the occurrence sits on.
        form_name: Name of the form that matched.

    Returns:
        The message naming the form, the line it sits on, and the fix.
    """
    matched_form = form_named(form_name)
    source_line = document_text.splitlines()[line_number - 1].strip()
    return CONTRAST_FRAMING_MESSAGE_TEMPLATE.format(
        name=form_name,
        text=source_line[:CONTRAST_FRAMING_QUOTED_LINE_LIMIT],
        guidance=matched_form.guidance,
    )
