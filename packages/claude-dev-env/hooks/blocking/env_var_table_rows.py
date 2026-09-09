"""Recognize Markdown environment-variable tables and parse their cells."""

from __future__ import annotations

import os
from collections.abc import Iterator

from hooks_constants.env_var_table_code_drift_constants import (
    ALL_CODE_FILE_EXTENSIONS,
    ALL_GENERIC_ENV_VAR_HEADERS,
    BACKTICK_TOKEN_PATTERN,
    CODE_FENCE_PATTERN,
    ENV_VAR_HEADER_PATTERN,
    ENV_VAR_HEADING_PATTERN,
    ENV_VAR_NAME_PATTERN,
    SEPARATOR_CELL_PATTERN,
    TABLE_ROW_PATTERN,
)


def _row_cells(table_line: str) -> list[str]:
    """Return the trimmed cells of one markdown table row.

    Args:
        table_line: A single line that begins with a pipe character.

    Returns:
        The text of each pipe-delimited cell, stripped, with the empty leading
        and trailing segments a bounding pipe produces removed.
    """
    stripped_line = table_line.strip()
    inner = stripped_line.strip("|")
    return [each_cell.strip() for each_cell in inner.split("|")]


def _first_backtick_token(cell_text: str) -> str | None:
    """Return the first backtick-wrapped token in a cell, when it has one.

    Args:
        cell_text: The trimmed text of a table cell.

    Returns:
        The text inside the first pair of backticks, or None when the cell
        carries no backtick-wrapped token.
    """
    token_match = BACKTICK_TOKEN_PATTERN.search(cell_text)
    if token_match is None:
        return None
    inner_text = token_match.group(1).strip()
    return inner_text or None


def _env_var_name_in_cell(cell_text: str) -> str | None:
    """Return the environment-variable name a cell names, when it names one.

    Args:
        cell_text: The trimmed text of a table cell.

    Returns:
        The UPPER_SNAKE variable name inside the first backticks, or None when
        the cell names no variable-shaped token.
    """
    token = _first_backtick_token(cell_text)
    if token is None:
        return None
    if ENV_VAR_NAME_PATTERN.match(token) is None:
        return None
    return token


def _code_file_reference_in_cell(cell_text: str) -> str | None:
    """Return the code-file path a cell names, when it names one.

    Args:
        cell_text: The trimmed text of a table cell.

    Returns:
        The relative code-file path inside the first backticks, or None when the
        token carries no recognized code-file extension.
    """
    token = _first_backtick_token(cell_text)
    if token is None:
        return None
    _, extension = os.path.splitext(token)
    if extension.lower() not in ALL_CODE_FILE_EXTENSIONS:
        return None
    return token


def _is_separator_row(all_cells: list[str]) -> bool:
    """Return whether every cell is a markdown table header-separator cell.

    Args:
        all_cells: The trimmed cells of one table row.

    Returns:
        True when each cell holds only dashes, colons, and whitespace.
    """
    return all(SEPARATOR_CELL_PATTERN.match(each_cell) is not None for each_cell in all_cells)


def iter_env_var_table_rows(content: str) -> Iterator[str]:
    """Yield environment-table rows and headerless edit fragments outside code fences."""
    is_inside_code_fence = False
    is_environment_table: bool | None = None
    is_environment_section = False
    for each_line in content.splitlines():
        if CODE_FENCE_PATTERN.match(each_line) is not None:
            is_inside_code_fence = not is_inside_code_fence
            is_environment_table = None
            continue
        if is_inside_code_fence:
            continue
        if each_line.lstrip().startswith("#"):
            is_environment_section = ENV_VAR_HEADING_PATTERN.search(each_line) is not None
        if TABLE_ROW_PATTERN.match(each_line) is None:
            is_environment_table = None
            continue
        all_cells = _row_cells(each_line)
        if not all_cells or _is_separator_row(all_cells):
            continue
        if is_environment_table is None:
            header = all_cells[0].strip("`* ")
            is_environment_table = (
                ENV_VAR_HEADER_PATTERN.fullmatch(header) is not None
                or _env_var_name_in_cell(all_cells[0]) is not None
                or (is_environment_section and header.casefold() in ALL_GENERIC_ENV_VAR_HEADERS)
            )
        if is_environment_table:
            yield each_line
