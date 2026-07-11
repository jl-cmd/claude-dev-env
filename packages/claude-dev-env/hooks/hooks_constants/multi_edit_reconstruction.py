"""Shared helpers that reconstruct the post-edit content of an Edit or MultiEdit.

Several PreToolUse blockers judge the content a write would leave on disk rather
than the raw payload fragment, so an edit on a line the blocker watches still
participates even when an untouched line elsewhere supplies the context. Both the
edit-replacement applier and the edit-list extractor are identical across those
blockers, so they live here once and are imported from each.
"""

from __future__ import annotations

__all__ = [
    "apply_edits",
    "edits_for_tool",
]


def apply_edits(existing_content: str, all_edits: list[dict]) -> str:
    """Return *existing_content* with each Edit/MultiEdit replacement applied in order.

    Args:
        existing_content: The current on-disk file content.
        all_edits: The Edit payload (as a single-element list) or MultiEdit
            ``edits`` list, each a mapping with an ``old_string`` and a
            ``new_string``.

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


def edits_for_tool(tool_name: str, tool_input: dict) -> list[dict]:
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
