"""Quote-aware tokenizing of a shell command for the verified-commit gate.

::

    echo "Next: git commit"   -> the quoted "git" is prose, not gated
    "git" commit               -> the quoted "git" is a wrapper-quoted binary, gated

The gate reads a raw command string, so it needs its own lightweight
quote-awareness to tell a real ``git`` invocation from a ``git`` word sitting
inside a quoted commit message, a ``gh pr comment`` body, or an ``echo``.
"""

from __future__ import annotations

import re

from config.verified_commit_constants import ALL_GIT_BINARY_NAMES


def collapse_line_continuations(command_text: str) -> str:
    """Remove backslash-newline line continuations the shell would erase.

    Bash joins a line continuation by deleting both characters, so
    ``git \\<newline>commit`` runs as a plain ``git commit``. Stripping the
    pair before tokenizing makes the token stream match what the shell
    executes.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        The command with every backslash-newline pair removed.
    """
    return re.sub(r"\\\r?\n", "", command_text)


def quoted_spans(command_text: str) -> list[tuple[int, int]]:
    """Find the character spans of every quoted region in a command.

    Scans single- and double-quoted runs left to right so a verb sitting
    inside a quoted ``-m`` commit message is recognised as message text
    rather than a real shell directory change.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        The ``(start, end)`` span of each quoted region, in order.
    """
    quoted_region_pattern = re.compile(r"\"[^\"]*\"|'[^']*'")
    return [
        (each_match.start(), each_match.end())
        for each_match in quoted_region_pattern.finditer(command_text)
    ]


def is_inside_quoted_region(position: int, all_quoted_spans: list[tuple[int, int]]) -> bool:
    """Decide whether a position falls inside any quoted region.

    Args:
        position: A character offset into the command string.
        all_quoted_spans: The quoted-region spans from ``quoted_spans``.

    Returns:
        True when the offset sits within a quoted region's bounds.
    """
    for each_span_start, each_span_end in all_quoted_spans:
        if each_span_start <= position < each_span_end:
            return True
    return False


def containing_quoted_span(
    position: int, all_quoted_spans: list[tuple[int, int]]
) -> tuple[int, int] | None:
    """Return the quoted region a position falls inside, or None.

    Args:
        position: A character offset into the command string.
        all_quoted_spans: The quoted-region spans from ``quoted_spans``.

    Returns:
        The ``(start, end)`` span containing the offset, or None when the
        offset sits outside every quoted region.
    """
    for each_span_start, each_span_end in all_quoted_spans:
        if each_span_start <= position < each_span_end:
            return (each_span_start, each_span_end)
    return None


def strip_token_quotes(token_text: str) -> str:
    """Remove quote characters from a token's edges.

    Tokens cut from inside a quoted shell-wrapper argument can carry an
    unpaired edge quote (``push"``), so both edges are stripped rather
    than only matched pairs.

    Args:
        token_text: One quote-aware token from a command string.

    Returns:
        The token without leading or trailing quote characters.
    """
    return token_text.strip("\"'")


def _quoted_final_path_segment(command_text: str, all_quoted_span_bounds: tuple[int, int]) -> str:
    """Read the lowercased final path segment of a quoted region's content."""
    span_start, span_end = all_quoted_span_bounds
    quoted_content = strip_token_quotes(command_text[span_start:span_end])
    return re.split(r"[\\/]", quoted_content)[-1].lower()


def git_word_match_gates(
    git_word_match: re.Match[str],
    command_text: str,
    all_quoted_spans: list[tuple[int, int]],
) -> bool:
    """Decide whether a ``git`` word match counts as a real invocation.

    ::

        echo "Next: git commit"   -> quoted prose, not gated
        "git" commit               -> quoted binary path, gated

    A ``git`` word outside every quoted region always gates. Inside a quoted
    region it gates only when the region's final ``[\\/]``-split path segment
    is ``git`` or ``git.exe``.

    Args:
        git_word_match: A ``git`` word match in the command.
        command_text: The raw command string from the tool payload.
        all_quoted_spans: The quoted-region spans from ``quoted_spans``.

    Returns:
        True when the matched ``git`` word counts as a real git invocation.
    """
    containing_span = containing_quoted_span(git_word_match.start(), all_quoted_spans)
    if containing_span is None:
        return True
    return _quoted_final_path_segment(command_text, containing_span) in ALL_GIT_BINARY_NAMES
