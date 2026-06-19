#!/usr/bin/env python3
"""PreToolUse hook: blocks a per-directory CLAUDE.md table that names a file absent from its subtree.

A per-directory ``CLAUDE.md`` documents the files reachable from its own
directory in a markdown table whose first column names each file in backticks.
When a first-column cell names a bare filename that exists nowhere under the scan
root (the CLAUDE.md directory's parent, which covers the directory, its
subdirectories, and its siblings), the table points a reader at a file that is
not there. This hook fires on Write, Edit, and MultiEdit targeting a file named
``CLAUDE.md`` and blocks the write when any such cell names a file absent from
the scan root. A table block whose own region declares an explicit relative-path
source (a ``../`` token) documents files outside the subtree, so that block's
rows are left alone — the exemption is scoped to the block, not the whole file.
"""

import json
import os
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.claude_md_orphan_file_blocker_constants import (  # noqa: E402
    ALL_REFERENCED_FILE_EXTENSIONS,
    CLAUDE_MD_FILENAME,
    FIRST_COLUMN_BACKTICK_PATTERN,
    MAX_ORPHAN_FILE_ISSUES,
    MAX_SUBTREE_FILES_SCANNED,
    ORPHAN_FILE_ADDITIONAL_CONTEXT,
    ORPHAN_FILE_MESSAGE_TEMPLATE,
    ORPHAN_FILE_SYSTEM_MESSAGE,
    RELATIVE_PATH_SOURCE_PATTERN,
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
        The text between the leading pipe and the next pipe, stripped of
        surrounding whitespace; an empty string when no cell is present.
    """
    after_leading_pipe = table_line.strip().lstrip("|")
    first_cell, _, _ = after_leading_pipe.partition("|")
    return first_cell.strip()


def _referenced_filename_in_cell(cell_text: str) -> str | None:
    """Return the bare filename a table cell references, when it has one.

    A cell references a bare filename only when its first backticked token has no
    path separator, is not a slash-command, and carries a known file extension.
    Subdirectory cells (trailing slash) and paths fall outside this scope and
    yield None.

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
    if not inner_text:
        return None
    if inner_text.startswith("/"):
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

    A ``../`` token signals that a table documents files in a sibling tree,
    referenced by path rather than living in the CLAUDE.md's own subtree. The
    block that carries such a token is out of scope, since its files legitimately
    sit outside the subtree.

    Args:
        text: A table block together with the prose that introduces it.

    Returns:
        True when *text* contains a ``../`` relative-path token.
    """
    return RELATIVE_PATH_SOURCE_PATTERN.search(text) is not None


def find_referenced_filenames(content: str) -> list[str]:
    """Return each bare filename a CLAUDE.md table references, in order.

    Walks the content line by line, grouping it into table blocks. A table block
    is a maximal run of consecutive markdown table rows; the prose lines since the
    previous block introduce it. A block whose introducing region or own rows
    declare an explicit relative-path source (a ``../`` token) documents files in
    a sibling tree, so its rows are skipped — the exemption is scoped to the
    block, not the whole file. Every remaining block contributes the bare filename
    each first-column cell names.

    Args:
        content: The CLAUDE.md content being written.

    Returns:
        Each referenced filename from a non-exempt table block, in the order it
        appears; duplicates preserved.
    """
    referenced_filenames: list[str] = []
    pending_region: list[str] = []
    current_block: list[str] = []
    for each_line in content.splitlines():
        if TABLE_ROW_PATTERN.match(each_line) is not None:
            current_block.append(each_line)
            continue
        if current_block:
            referenced_filenames.extend(_block_filenames(pending_region, current_block))
            current_block = []
            pending_region = []
        pending_region.append(each_line)
    referenced_filenames.extend(_block_filenames(pending_region, current_block))
    return referenced_filenames


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
    block_region = "\n".join(all_region_lines + all_block_lines)
    if _declares_relative_path_source(block_region):
        return []
    block_filenames: list[str] = []
    for each_line in all_block_lines:
        each_filename = _filename_in_table_row(each_line)
        if each_filename is not None:
            block_filenames.append(each_filename)
    return block_filenames


def _resolve_scan_root(claude_md_directory: Path) -> Path:
    """Return the directory whose subtree bounds the filename existence search.

    The search root is the CLAUDE.md directory's parent when that parent exists,
    so a table that documents files in a sibling directory or one level up still
    resolves them. When the directory has no distinct parent, the CLAUDE.md
    directory itself is the root.

    Args:
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        The directory to walk when collecting candidate filenames.
    """
    parent_directory = claude_md_directory.parent
    if parent_directory == claude_md_directory:
        return claude_md_directory
    return parent_directory


def _filenames_in_subtree(claude_md_directory: Path) -> set[str]:
    """Return the set of file basenames reachable from the CLAUDE.md directory.

    Walks the subtree rooted at the CLAUDE.md directory's parent (or the
    directory itself when it has no distinct parent), collecting each file's
    basename. The wider parent root resolves files a table documents in a sibling
    directory or one level up. The walk is bounded so a large tree never stalls a
    write.

    Args:
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        Each file basename found under the scan root, capped at the scan budget.
    """
    scan_root = _resolve_scan_root(claude_md_directory)
    all_basenames: set[str] = set()
    scanned_count = 0
    for each_path in scan_root.rglob("*"):
        if not each_path.is_file():
            continue
        all_basenames.add(each_path.name)
        scanned_count += 1
        if scanned_count >= MAX_SUBTREE_FILES_SCANNED:
            break
    return all_basenames


def find_missing_filenames(content: str, claude_md_directory: Path) -> list[str]:
    """Return the referenced filenames absent from the CLAUDE.md's scan root.

    A referenced filename is missing when it exists nowhere under the scan root
    — the CLAUDE.md directory's parent (or the directory itself when it has no
    distinct parent), which covers the directory, its subdirectories, and its
    siblings. A table block that declares an explicit relative-path source (a
    ``../`` token in the block or the prose that introduces it) yields no findings
    for that block's rows, since those files legitimately live elsewhere; an
    unrelated block in the same file is still checked.

    Args:
        content: The CLAUDE.md content being written.
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        Each referenced filename with no matching file under the scan root, in
        first-seen order with duplicates removed, capped at the issue budget.
    """
    subtree_filenames = _filenames_in_subtree(claude_md_directory)
    missing_filenames: list[str] = []
    already_reported: set[str] = set()
    for each_filename in find_referenced_filenames(content):
        if each_filename in already_reported:
            continue
        if each_filename in subtree_filenames:
            continue
        already_reported.add(each_filename)
        missing_filenames.append(each_filename)
        if len(missing_filenames) >= MAX_ORPHAN_FILE_ISSUES:
            break
    return missing_filenames


def _read_existing_file_content(file_path: str) -> str | None:
    """Return the current on-disk content of *file_path*, or None when unreadable.

    Args:
        file_path: The path of the file the edit targets.

    Returns:
        The file's text, or None when the file is missing or cannot be decoded.
    """
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _apply_edits(existing_content: str, all_edits: list[dict]) -> str:
    """Return *existing_content* with each MultiEdit replacement applied in order.

    Args:
        existing_content: The current on-disk file content.
        all_edits: The MultiEdit ``edits`` list, each a mapping with an
            ``old_string`` and a ``new_string``.

    Returns:
        The content after replacing the first occurrence of each edit's
        ``old_string`` with its ``new_string``, in list order.
    """
    edited_content = existing_content
    for each_edit in all_edits:
        if not isinstance(each_edit, dict):
            continue
        old_string = each_edit.get("old_string", "")
        new_string = each_edit.get("new_string", "")
        if isinstance(old_string, str) and isinstance(new_string, str) and old_string:
            edited_content = edited_content.replace(old_string, new_string, 1)
    return edited_content


def _edit_fragments(all_edits: list[dict]) -> list[str]:
    """Return each MultiEdit ``new_string`` fragment present as a non-empty string.

    Args:
        all_edits: The MultiEdit ``edits`` list.

    Returns:
        Every ``new_string`` value that is a non-empty string, in list order.
    """
    all_fragments: list[str] = []
    for each_edit in all_edits:
        if not isinstance(each_edit, dict):
            continue
        new_string = each_edit.get("new_string", "")
        if isinstance(new_string, str) and new_string:
            all_fragments.append(new_string)
    return all_fragments


def _candidate_contents(tool_name: str, tool_input: dict, file_path: str) -> list[str]:
    """Return the post-edit content the relative-path exemption keys off.

    For Write the candidate is the full new content. For Edit and MultiEdit the
    candidate is the existing file with the replacements applied, so a ``../``
    source line outside the edited rows still exempts that table block. When the
    existing file cannot be read, the raw ``new_string`` fragment(s) are evaluated
    so an orphan introduced by the edit itself is still caught.

    Args:
        tool_name: The intercepted tool — ``Write``, ``Edit``, or ``MultiEdit``.
        tool_input: The tool's input payload.
        file_path: The destination path of the write or edit.

    Returns:
        Each content string to scan; an empty list when none are present.
    """
    if tool_name == "Write":
        content = tool_input.get("content", "")
        return [content] if isinstance(content, str) and content else []
    all_edits = _edits_for_tool(tool_name, tool_input)
    existing_content = _read_existing_file_content(file_path)
    if existing_content is None:
        return _edit_fragments(all_edits)
    return [_apply_edits(existing_content, all_edits)]


def _edits_for_tool(tool_name: str, tool_input: dict) -> list[dict]:
    """Return the edit mappings an Edit or MultiEdit payload carries.

    Args:
        tool_name: The intercepted tool — ``Edit`` or ``MultiEdit``.
        tool_input: The tool's input payload.

    Returns:
        A single-element list holding the Edit payload, or the MultiEdit
        ``edits`` list when it is present as a list; an empty list otherwise.
    """
    if tool_name == "Edit":
        return [tool_input]
    all_edits = tool_input.get("edits", [])
    return all_edits if isinstance(all_edits, list) else []


def _collect_missing_filenames(
    all_candidate_contents: list[str], claude_md_directory: Path
) -> list[str]:
    """Return every missing referenced filename across all candidate contents.

    Args:
        all_candidate_contents: The content strings the tool would write.
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        Each missing filename in first-seen order with duplicates removed,
        capped at the issue budget.
    """
    missing_filenames: list[str] = []
    already_reported: set[str] = set()
    for each_content in all_candidate_contents:
        for each_filename in find_missing_filenames(each_content, claude_md_directory):
            if each_filename in already_reported:
                continue
            already_reported.add(each_filename)
            missing_filenames.append(each_filename)
            if len(missing_filenames) >= MAX_ORPHAN_FILE_ISSUES:
                return missing_filenames
    return missing_filenames


def _build_block_payload(all_missing_filenames: list[str], directory: str) -> dict:
    """Build the PreToolUse deny payload listing each missing filename.

    Args:
        all_missing_filenames: The referenced filenames absent from the subtree.
        directory: The directory that holds the target CLAUDE.md.

    Returns:
        The hook-result dictionary the harness reads to deny the write.
    """
    formatted_missing = ", ".join(f"`{each_name}`" for each_name in all_missing_filenames)
    reason = ORPHAN_FILE_MESSAGE_TEMPLATE.format(directory=directory, missing=formatted_missing)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": ORPHAN_FILE_ADDITIONAL_CONTEXT,
        },
        "systemMessage": ORPHAN_FILE_SYSTEM_MESSAGE,
        "suppressOutput": True,
    }


def _emit_hook_result(all_hook_data: dict, output_stream: TextIO) -> None:
    """Write the hook result JSON to the given output stream.

    Args:
        all_hook_data: The hook-result dictionary to serialize.
        output_stream: The stream the harness reads the decision from.
    """
    output_stream.write(json.dumps(all_hook_data) + "\n")
    output_stream.flush()


def main() -> None:
    """Read the PreToolUse payload from stdin and block an orphan-file CLAUDE.md."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not isinstance(input_data, dict):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if not isinstance(tool_name, str):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not is_claude_md_file(file_path):
        sys.exit(0)

    claude_md_directory = Path(file_path).resolve().parent
    if not claude_md_directory.is_dir():
        sys.exit(0)

    all_candidate_contents = _candidate_contents(tool_name, tool_input, file_path)
    if not all_candidate_contents:
        sys.exit(0)

    missing_filenames = _collect_missing_filenames(all_candidate_contents, claude_md_directory)
    if not missing_filenames:
        sys.exit(0)

    block_payload = _build_block_payload(missing_filenames, str(claude_md_directory))
    _emit_hook_result(block_payload, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
