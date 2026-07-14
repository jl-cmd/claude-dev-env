"""Extract the file references a per-directory CLAUDE.md makes.

Two kinds of reference are collected: a bare filename a first-column table cell
names in backticks, and a script an interpreter invocation inside a fenced run
command names (``python script.py``). A table block or run-command fence that
declares an explicit ``../`` relative-path source is left alone.
"""

import os

from claude_md_orphan_file_blocker_parts.config.orphan_blocker_constants import (
    NEWLINE_JOIN_SEPARATOR,
)

from hooks_constants.claude_md_orphan_file_blocker_constants import (
    ALL_REFERENCED_FILE_EXTENSIONS,
    ALL_RUN_COMMAND_SCRIPT_EXTENSIONS,
    CLAUDE_MD_FILENAME,
    CODE_FENCE_PATTERN,
    FIRST_COLUMN_BACKTICK_PATTERN,
    REGION_BOUNDARY_PATTERN,
    RELATIVE_PATH_SOURCE_PATTERN,
    RUN_COMMAND_SCRIPT_PATTERN,
    SEPARATOR_CELL_PATTERN,
    TABLE_ROW_PATTERN,
)


def is_claude_md_file(file_path: str) -> bool:
    """Return whether *file_path* names a per-directory ``CLAUDE.md`` file.

    Args:
        file_path: The destination path of the write or edit.

    Returns:
        True when the path's basename is exactly ``CLAUDE.md``.
    """
    return os.path.basename(file_path) == CLAUDE_MD_FILENAME


def _first_table_cell(table_line: str) -> str:
    """Return the trimmed text of the first column cell in a markdown table row.

    Args:
        table_line: A single line that begins with a pipe character.

    Returns:
        The text between the leading pipe and the next pipe, stripped.
    """
    after_leading_pipe = table_line.strip().lstrip("|")
    first_cell, _, _ = after_leading_pipe.partition("|")
    return first_cell.strip()


def _referenced_filename_in_cell(cell_text: str) -> str | None:
    """Return the bare filename a table cell references, when it has one.

    A cell references a bare filename only when its first backticked token has no
    path separator, is not a slash-command, and carries a known file extension.

    Args:
        cell_text: The trimmed text of a first-column table cell.

    Returns:
        The bare filename to verify in the subtree, or None when the cell names
        no bare file.
    """
    backtick_match = FIRST_COLUMN_BACKTICK_PATTERN.search(cell_text)
    if backtick_match is None:
        return None
    inner_text = backtick_match.group(1).strip()
    if not inner_text or inner_text.startswith("/"):
        return None
    if "/" in inner_text or "\\" in inner_text:
        return None
    _, extension = os.path.splitext(inner_text)
    if extension.lower() not in ALL_REFERENCED_FILE_EXTENSIONS:
        return None
    return inner_text


def _filename_in_table_row(table_line: str) -> str | None:
    """Return the bare filename a markdown table row references, when it has one.

    Args:
        table_line: A single line that begins with a pipe character.

    Returns:
        The bare filename in the row's first column, or None when the row is a
        header-separator row or names no bare file.
    """
    first_cell = _first_table_cell(table_line)
    if not first_cell or SEPARATOR_CELL_PATTERN.match(first_cell):
        return None
    return _referenced_filename_in_cell(first_cell)


def _declares_relative_path_source(text: str) -> bool:
    """Return whether *text* declares an explicit relative-path file source.

    Args:
        text: A table block together with the prose that introduces it.

    Returns:
        True when *text* contains a ``../`` relative-path token.
    """
    return RELATIVE_PATH_SOURCE_PATTERN.search(text) is not None


def _block_filenames(all_region_lines: list[str], all_block_lines: list[str]) -> list[str]:
    """Return the bare filenames a table block contributes, honoring its exemption.

    Args:
        all_region_lines: The prose lines accumulated before this block.
        all_block_lines: The consecutive table rows that form the block.

    Returns:
        Each bare filename the block's first-column cells name, or an empty list
        when the block (with its introducing region) declares a ``../`` source.
    """
    if not all_block_lines:
        return []
    block_region = NEWLINE_JOIN_SEPARATOR.join(all_region_lines + all_block_lines)
    if _declares_relative_path_source(block_region):
        return []
    block_filenames: list[str] = []
    for each_line in all_block_lines:
        each_filename = _filename_in_table_row(each_line)
        if each_filename is not None:
            block_filenames.append(each_filename)
    return block_filenames


def find_referenced_filenames(content: str) -> list[str]:
    """Return each bare filename a CLAUDE.md table references, in order.

    Args:
        content: The CLAUDE.md content being written.

    Returns:
        Each referenced filename from a non-exempt table block, in order.
    """
    referenced_filenames: list[str] = []
    pending_region: list[str] = []
    current_block: list[str] = []
    is_inside_code_fence = False
    for each_line in content.splitlines():
        if CODE_FENCE_PATTERN.match(each_line) is not None:
            is_inside_code_fence = not is_inside_code_fence
            continue
        if is_inside_code_fence:
            continue
        if TABLE_ROW_PATTERN.match(each_line) is not None:
            current_block.append(each_line)
            continue
        if current_block:
            referenced_filenames.extend(_block_filenames(pending_region, current_block))
            current_block, pending_region = [], []
        if REGION_BOUNDARY_PATTERN.match(each_line) is not None:
            pending_region = []
        pending_region.append(each_line)
    referenced_filenames.extend(_block_filenames(pending_region, current_block))
    return referenced_filenames


def _script_basename_from_token(script_token: str) -> str | None:
    """Return the bare basename one captured script token names, when it has one.

    A path-qualified script keeps only its final segment. A script named by an
    explicit ``../`` relative-path source is exempt and yields None, as does a
    token whose basename carries no recognized script extension.

    Args:
        script_token: One script path captured from an interpreter invocation.

    Returns:
        The bare script basename, or None when the token is relative-path-sourced
        or carries no recognized extension.
    """
    if _declares_relative_path_source(script_token):
        return None
    basename = os.path.basename(script_token.replace("\\", "/").rstrip("/"))
    if not basename:
        return None
    _, extension = os.path.splitext(basename)
    if extension.lower() not in ALL_RUN_COMMAND_SCRIPT_EXTENSIONS:
        return None
    return basename


def _next_quote_state(open_quote_character: str, each_character: str) -> str:
    """Return the open-quote state after reading one character.

    Args:
        open_quote_character: The currently open quote character, or empty.
        each_character: The character just read.

    Returns:
        The empty string when a matching close quote is read, the character when
        it opens a quote, or the unchanged state otherwise.
    """
    if open_quote_character:
        return "" if each_character == open_quote_character else open_quote_character
    if each_character in ("'", '"'):
        return each_character
    return open_quote_character


def _command_text_before_comment(fenced_line: str) -> str:
    """Return the runnable portion of a fenced line, with any shell comment removed.

    A shell comment starts at a ``#`` that begins a word outside any quoted span
    and runs to end of line; the text from that ``#`` is dropped.

    Args:
        fenced_line: A single line drawn from inside a fenced code block.

    Returns:
        The line truncated at its first unquoted word-leading ``#``, or the whole
        line when it carries no such comment marker.
    """
    open_quote_character = ""
    previous_character = ""
    for each_index, each_character in enumerate(fenced_line):
        starts_word = each_index == 0 or previous_character.isspace()
        if not open_quote_character and each_character == "#" and starts_word:
            return fenced_line[:each_index]
        open_quote_character = _next_quote_state(open_quote_character, each_character)
        previous_character = each_character
    return fenced_line


def _run_command_filenames_in_line(fenced_line: str) -> list[str]:
    """Return each script basename the interpreter invocations on this line name.

    A shell comment's text contributes nothing; a chained line contributes each
    invocation's basename in order.

    Args:
        fenced_line: A single line drawn from inside a fenced code block.

    Returns:
        Each bare script basename the line's invocations name, in order.
    """
    runnable_text = _command_text_before_comment(fenced_line)
    line_filenames: list[str] = []
    for each_match in RUN_COMMAND_SCRIPT_PATTERN.finditer(runnable_text):
        each_basename = _script_basename_from_token(each_match.group(1).strip())
        if each_basename is not None:
            line_filenames.append(each_basename)
    return line_filenames


class _RunCommandScan:
    """Walks CLAUDE.md lines and collects the script basenames fenced run commands name.

    Attributes:
        filenames: The script basenames collected so far, in order.
    """

    def __init__(self) -> None:
        self.filenames: list[str] = []
        self._pending_region: list[str] = []
        self._is_inside_fence = False
        self._is_region_relative_path_sourced = False

    def _toggle_fence(self) -> None:
        """Open or close the current fence, capturing its region's ``../`` source flag."""
        if not self._is_inside_fence:
            self._is_region_relative_path_sourced = _declares_relative_path_source(
                NEWLINE_JOIN_SEPARATOR.join(self._pending_region)
            )
        else:
            self._pending_region = []
        self._is_inside_fence = not self._is_inside_fence

    def consume(self, each_line: str) -> None:
        """Fold one CLAUDE.md line into the scan state.

        Args:
            each_line: The next line of the CLAUDE.md content.
        """
        if CODE_FENCE_PATTERN.match(each_line) is not None:
            self._toggle_fence()
            return
        if self._is_inside_fence:
            if not self._is_region_relative_path_sourced:
                self.filenames.extend(_run_command_filenames_in_line(each_line))
            return
        if REGION_BOUNDARY_PATTERN.match(each_line) is not None:
            self._pending_region = []
        self._pending_region.append(each_line)


def find_run_command_filenames(content: str) -> list[str]:
    """Return each script basename a fenced run command invokes, in order.

    Args:
        content: The CLAUDE.md content being written.

    Returns:
        Each script basename a fenced run command names, in the order it appears.
    """
    scan = _RunCommandScan()
    for each_line in content.splitlines():
        scan.consume(each_line)
    return scan.filenames
