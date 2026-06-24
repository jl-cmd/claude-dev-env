"""Shared text-stripping helper for the Stop-hook prose blockers.

Several Stop hooks judge the prose of an assistant message and must ignore
fenced code blocks, inline code spans, and leading blockquotes so a phrase that
appears only inside code or a quote never trips the detector. The stripping
logic is identical across those blockers, so it lives here once and is imported
from each.
"""

from __future__ import annotations

import re

__all__ = [
    "strip_code_and_quotes",
]

CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)
INLINE_CODE_PATTERN = re.compile(r"`[^`]+`")
QUOTED_BLOCK_PATTERN = re.compile(r"^>.*$", re.MULTILINE)


def strip_code_and_quotes(text: str) -> str:
    """Remove fenced code blocks, inline code, and blockquotes from prose.

    Args:
        text: The raw assistant message to clean of code and quoted lines.

    Returns:
        The text with every fenced code block, inline code span, and leading
        blockquote line removed, so only the prose a reader sees remains.
    """
    text = CODE_BLOCK_PATTERN.sub("", text)
    text = INLINE_CODE_PATTERN.sub("", text)
    text = QUOTED_BLOCK_PATTERN.sub("", text)
    return text
