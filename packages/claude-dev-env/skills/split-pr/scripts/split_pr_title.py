"""Normalize split-PR titles to exactly one conventional commit prefix.

::

    normalize_split_title("feat: foo") -> "feat: foo"
    normalize_split_title("feat: feat: foo") -> "feat: foo"
    normalize_split_title("bare title") -> "chore: bare title"
"""

from __future__ import annotations

import re

from config.plan_constants import (
    CONVENTIONAL_PREFIX_PATTERN,
    DEFAULT_TITLE_PREFIX,
    TITLE_PREFIX_SEPARATOR,
)


def normalize_split_title(raw_title: str) -> str:
    """Return a title with exactly one conventional-commit prefix.

    Args:
        raw_title: Candidate title that may lack a prefix or stack several.

    Returns:
        Title of the form ``<prefix>: <remainder>`` with one prefix only.
    """
    prefix_pattern = re.compile(CONVENTIONAL_PREFIX_PATTERN, re.IGNORECASE)
    remainder = raw_title.strip()
    chosen_prefix = DEFAULT_TITLE_PREFIX
    while True:
        match = prefix_pattern.match(remainder)
        if match is None:
            break
        chosen_prefix = match.group("prefix").lower()
        remainder = remainder[match.end() :].lstrip()
    if not remainder:
        remainder = "split slice"
    return f"{chosen_prefix}{TITLE_PREFIX_SEPARATOR}{remainder}"
