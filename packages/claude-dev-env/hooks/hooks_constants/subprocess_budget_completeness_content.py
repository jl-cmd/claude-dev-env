"""Resolve the post-edit content a Write, Edit, or MultiEdit payload leaves on disk.

Shared by subprocess_budget_completeness.py, which parses this content's AST to
find a named budget helper that omits a reachable subprocess timeout.
"""

from __future__ import annotations

from hooks_constants.multi_edit_reconstruction import apply_edits, edits_for_tool

__all__ = [
    "existing_file_content",
    "reconstructed_edit_content",
    "reconstructed_multi_edit_content",
    "resolved_content",
]


def existing_file_content(file_path: str) -> str | None:
    try:
        with open(file_path, "r", encoding="utf-8") as existing_file:
            return existing_file.read()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None


def reconstructed_edit_content(all_tool_input_fields: dict[str, object]) -> str:
    file_path = all_tool_input_fields.get("file_path")
    old_string = all_tool_input_fields.get("old_string")
    new_string = all_tool_input_fields.get("new_string")
    if not isinstance(file_path, str) or not isinstance(old_string, str):
        return ""
    if not isinstance(new_string, str) or not old_string:
        return ""
    existing_content = existing_file_content(file_path)
    if existing_content is None or old_string not in existing_content:
        return ""
    return apply_edits(existing_content, edits_for_tool("Edit", all_tool_input_fields))


def reconstructed_multi_edit_content(
    all_tool_input_fields: dict[str, object], all_edits: list[object]
) -> str:
    """Return the whole file MultiEdit's edit list would leave on disk.

    Args:
        all_tool_input_fields: The MultiEdit payload's tool_input mapping.
        all_edits: The payload's ``edits`` list.

    Returns:
        The reconstructed content, or an empty string when the target file
        cannot be read.
    """
    file_path = all_tool_input_fields.get("file_path")
    if not isinstance(file_path, str):
        return ""
    existing_content = existing_file_content(file_path)
    if existing_content is None:
        return ""
    all_edit_dicts = [each_edit for each_edit in all_edits if isinstance(each_edit, dict)]
    return apply_edits(existing_content, all_edit_dicts)


def resolved_content(all_tool_input_fields: dict[str, object]) -> str:
    written_content = all_tool_input_fields.get("content")
    if isinstance(written_content, str):
        return written_content
    all_edits = all_tool_input_fields.get("edits")
    if isinstance(all_edits, list):
        return reconstructed_multi_edit_content(all_tool_input_fields, all_edits)
    return reconstructed_edit_content(all_tool_input_fields)
