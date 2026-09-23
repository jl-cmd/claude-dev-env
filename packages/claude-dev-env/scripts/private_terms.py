"""Find private organization names in text without holding the names.

``private_term_line_numbers`` reports where a name appears and never the
name, so a caller can print its result in a public log.
"""

from __future__ import annotations

import bisect
import hashlib
from collections.abc import Collection

from dev_env_scripts_constants.private_term_constants import (
    ALL_PRIVATE_TERM_DIGESTS,
    PRIVATE_TERM_TEXT_ENCODING,
    PrivateTermDigest,
)


def _normalized_text_and_line_starts(text: str) -> tuple[str, list[int]]:
    all_normalized_lines: list[str] = []
    all_line_starts: list[int] = []
    offset = 0
    for each_line in text.split("\n"):
        normalized_line = "".join(
            each_character
            for each_character in each_line.lower()
            if each_character.isascii() and each_character.isalnum()
        )
        all_line_starts.append(offset)
        all_normalized_lines.append(normalized_line)
        offset += len(normalized_line)
    return "".join(all_normalized_lines), all_line_starts


def _matching_window_starts(
    normalized_text: str, length: int, all_wanted_digests: set[str]
) -> list[int]:
    return [
        each_start
        for each_start in range(len(normalized_text) - length + 1)
        if hashlib.sha256(
            normalized_text[each_start : each_start + length].encode(
                PRIVATE_TERM_TEXT_ENCODING
            )
        ).hexdigest()
        in all_wanted_digests
    ]


def private_term_line_numbers(
    text: str,
    all_term_digests: Collection[PrivateTermDigest] = ALL_PRIVATE_TERM_DIGESTS,
) -> tuple[int, ...]:
    """Return the sorted one-based line numbers where a private name starts.

    Args:
        text: Text to scan.
        all_term_digests: Digests of the normalized names to find.

    Returns:
        Each line number once. A name that wraps onto the next line reports
        the line where it starts.
    """
    normalized_text, all_line_starts = _normalized_text_and_line_starts(text)
    all_found_line_numbers: set[int] = set()
    for each_length in {each_digest.length for each_digest in all_term_digests}:
        all_wanted_digests = {
            each_digest.sha256
            for each_digest in all_term_digests
            if each_digest.length == each_length
        }
        all_found_line_numbers.update(
            bisect.bisect_right(all_line_starts, each_start)
            for each_start in _matching_window_starts(
                normalized_text, each_length, all_wanted_digests
            )
        )
    return tuple(sorted(all_found_line_numbers))


def names_private_term(
    text: str,
    all_term_digests: Collection[PrivateTermDigest] = ALL_PRIVATE_TERM_DIGESTS,
) -> bool:
    """Return whether the text names any private organization."""
    return bool(private_term_line_numbers(text, all_term_digests))
