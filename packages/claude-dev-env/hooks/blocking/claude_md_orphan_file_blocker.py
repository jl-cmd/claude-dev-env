#!/usr/bin/env python3
"""PreToolUse hook: blocks a per-directory CLAUDE.md table that names a file absent from its subtree.

A per-directory ``CLAUDE.md`` documents the files in its own directory subtree in
a markdown table whose first column names each file in backticks. When a
first-column cell names a bare filename that exists nowhere in that subtree (the
CLAUDE.md's own directory and every subdirectory of it), the table points a
reader at a file that is not there. This hook fires on Write, Edit, and MultiEdit
targeting a file named ``CLAUDE.md`` and blocks the write when any such cell
names a file absent from the subtree. A table whose content declares an explicit
relative-path source (a ``../`` token) documents files outside the subtree, so it
is left alone.
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


def find_referenced_filenames(content: str) -> list[str]:
    """Return each bare filename a CLAUDE.md table references, in order.

    Walks the content line by line, takes the first column of every markdown
    table row, skips header-separator rows, and collects the bare filename each
    qualifying cell names.

    Args:
        content: The CLAUDE.md content being written.

    Returns:
        Each referenced filename, in the order it appears; duplicates preserved.
    """
    referenced_filenames: list[str] = []
    for each_line in content.splitlines():
        if TABLE_ROW_PATTERN.match(each_line) is None:
            continue
        first_cell = _first_table_cell(each_line)
        if not first_cell or SEPARATOR_CELL_PATTERN.match(first_cell):
            continue
        each_filename = _referenced_filename_in_cell(first_cell)
        if each_filename is not None:
            referenced_filenames.append(each_filename)
    return referenced_filenames


def _declares_relative_path_source(content: str) -> bool:
    """Return whether the content declares an explicit relative-path file source.

    A ``../`` token signals that the table documents files in a sibling tree,
    referenced by path rather than living in the CLAUDE.md's own subtree. Such a
    table is out of scope, since its files legitimately sit outside the subtree.

    Args:
        content: The CLAUDE.md content being written.

    Returns:
        True when the content contains a ``../`` relative-path token.
    """
    return RELATIVE_PATH_SOURCE_PATTERN.search(content) is not None


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
    siblings. A table that declares an explicit relative-path source (a ``../``
    token) yields no findings, since those files legitimately live elsewhere.

    Args:
        content: The CLAUDE.md content being written.
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        Each referenced filename with no matching file under the scan root, in
        first-seen order with duplicates removed, capped at the issue budget.
    """
    if _declares_relative_path_source(content):
        return []
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


def _candidate_contents(tool_name: str, tool_input: dict) -> list[str]:
    """Return each content string the tool would write into the CLAUDE.md file.

    Args:
        tool_name: The intercepted tool — ``Write``, ``Edit``, or ``MultiEdit``.
        tool_input: The tool's input payload.

    Returns:
        The Write ``content``, the Edit ``new_string``, or each MultiEdit
        ``new_string``; an empty list when none are present as strings.
    """
    if tool_name == "Write":
        content = tool_input.get("content", "")
        return [content] if isinstance(content, str) and content else []
    if tool_name == "Edit":
        new_string = tool_input.get("new_string", "")
        return [new_string] if isinstance(new_string, str) and new_string else []
    all_edits = tool_input.get("edits", [])
    if not isinstance(all_edits, list):
        return []
    all_new_strings: list[str] = []
    for each_edit in all_edits:
        if not isinstance(each_edit, dict):
            continue
        new_string = each_edit.get("new_string", "")
        if isinstance(new_string, str) and new_string:
            all_new_strings.append(new_string)
    return all_new_strings


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

    all_candidate_contents = _candidate_contents(tool_name, tool_input)
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
