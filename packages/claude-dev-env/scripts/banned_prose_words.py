#!/usr/bin/env python3
"""Find banned emphasis words in authored prose.

The package AGENTS.md bans ``real``, ``really``, ``real-world``, ``actual``,
``actually``, ``genuine``, and ``true`` from every authored surface. This
module reports each occurrence that survives after code spans, paths, and
link targets are removed, so a caller can grade a document or a whole tree.

::

    all_hits = find_banned_prose_words("The real cause is a timeout.\n")
    ok: all_hits == [(1, "real")]
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from dev_env_scripts_constants.banned_prose_word_constants import (
    ADJECTIVAL_TRUE_PATTERN,
    ALL_EXEMPT_PATH_SEGMENTS,
    ALL_GOVERNED_PATH_SEGMENTS,
    ALL_GOVERNED_SUFFIXES,
    ALL_PREDICATIVE_TRUE_LEADS,
    BANNED_PROSE_WORD_PATTERN,
    BLANKED_SPAN,
    FENCED_CODE_PATTERN,
    INDENTED_CODE_PATTERN,
    INLINE_CODE_PATTERN,
    MARKDOWN_LINK_TARGET_PATTERN,
    PATH_PATTERN,
    URL_PATTERN,
    UTF8_ENCODING,
    XML_TAG_PATTERN,
)


def governs_path(relative_posix_path: str) -> bool:
    """Return whether the ban applies to one repository path.

    Args:
        relative_posix_path: Repository-relative path with forward slashes.

    Returns:
        True for an authored instruction surface the ban covers.
    """
    normalized_path = f"/{relative_posix_path.lower().lstrip('/')}"
    if PurePosixPath(normalized_path).suffix not in ALL_GOVERNED_SUFFIXES:
        return False
    if any(
        each_segment in normalized_path for each_segment in ALL_EXEMPT_PATH_SEGMENTS
    ):
        return False
    return any(
        each_segment in normalized_path for each_segment in ALL_GOVERNED_PATH_SEGMENTS
    )


def prose_lines(document_text: str) -> list[str]:
    """Return one prose line for each source line, with code spans blanked.

    Args:
        document_text: Full document source.

    Returns:
        Lines of the same count as the source, holding prose only.
    """
    all_prose_lines: list[str] = []
    is_inside_fence = False
    for each_line in document_text.splitlines():
        if FENCED_CODE_PATTERN.match(each_line):
            is_inside_fence = not is_inside_fence
            all_prose_lines.append("")
            continue
        if is_inside_fence or INDENTED_CODE_PATTERN.match(each_line):
            all_prose_lines.append("")
            continue
        prose_line = INLINE_CODE_PATTERN.sub(BLANKED_SPAN, each_line)
        prose_line = XML_TAG_PATTERN.sub(BLANKED_SPAN, prose_line)
        prose_line = MARKDOWN_LINK_TARGET_PATTERN.sub(BLANKED_SPAN, prose_line)
        prose_line = URL_PATTERN.sub(BLANKED_SPAN, prose_line)
        all_prose_lines.append(PATH_PATTERN.sub(BLANKED_SPAN, prose_line))
    return all_prose_lines


def _adjectival_true_columns(prose_line: str) -> list[int]:
    all_columns: list[int] = []
    for each_match in ADJECTIVAL_TRUE_PATTERN.finditer(prose_line):
        leading_words = prose_line[: each_match.start()].lower().split()
        if leading_words and leading_words[-1].strip(",;:(") in (
            ALL_PREDICATIVE_TRUE_LEADS
        ):
            continue
        all_columns.append(each_match.start() + 1)
    return all_columns


def find_banned_prose_words(document_text: str) -> list[tuple[int, int, str]]:
    """Return each banned word occurrence in authored prose.

    Args:
        document_text: Full document source.

    Returns:
        Ordered ``(line number, column, word)`` triples, both 1-based.
    """
    all_hits: list[tuple[int, int, str]] = []
    for each_line_number, each_prose_line in enumerate(prose_lines(document_text), 1):
        for each_match in BANNED_PROSE_WORD_PATTERN.finditer(each_prose_line):
            all_hits.append(
                (each_line_number, each_match.start() + 1, each_match.group(1).lower())
            )
        for each_column in _adjectival_true_columns(each_prose_line):
            all_hits.append((each_line_number, each_column, "true"))
    return sorted(all_hits)


def governed_paths(from_package_root: Path) -> list[str]:
    """Return every governed surface under one package root.

    Args:
        from_package_root: ``packages/claude-dev-env`` root.

    Returns:
        Sorted package-relative paths the ban covers.
    """
    all_paths: list[str] = []
    for each_path in from_package_root.rglob("*"):
        if not each_path.is_file():
            continue
        relative_path = each_path.relative_to(from_package_root).as_posix()
        if governs_path(relative_path):
            all_paths.append(relative_path)
    return sorted(all_paths)


def banned_prose_words_in_tree(
    from_package_root: Path,
) -> list[tuple[str, int, str]]:
    """Return every banned word occurrence across the governed surfaces.

    Args:
        from_package_root: ``packages/claude-dev-env`` root.

    Returns:
        Ordered ``(package-relative path, line number, word)`` triples.
    """
    all_hits: list[tuple[str, int, str]] = []
    for each_relative_path in governed_paths(from_package_root):
        document_text = (from_package_root / each_relative_path).read_text(
            encoding=UTF8_ENCODING, errors="replace"
        )
        for each_line_number, _column, each_word in find_banned_prose_words(
            document_text
        ):
            all_hits.append((each_relative_path, each_line_number, each_word))
    return all_hits
