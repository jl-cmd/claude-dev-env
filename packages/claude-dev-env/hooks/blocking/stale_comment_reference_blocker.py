#!/usr/bin/env python3
"""PreToolUse hook: blocks an Edit that rewrites a Python code line while keeping a contradicting comment above it.

Say a comment reads ``# Mock asyncio`` right above a line that patches
``asyncio.sleep``. An Edit that rewrites just that line to patch something
else, but leaves the comment untouched, orphans the comment: it still names
``asyncio``, but the code below no longer does. The same gap opens when the
Edit deletes the line outright instead of rewriting it. The hook locates
each occurrence of the edit's ``old_string`` in the file and reads the line
directly above it, denying the edit when that line is a standalone ``#``
comment naming an identifier ``old_string`` carries and ``new_string`` drops.
"""

import json
import re
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pre_tool_use_dispatcher_constants import EDIT_TOOL_NAME  # noqa: E402
from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin  # noqa: E402
from hooks_constants.stale_comment_reference_blocker_constants import (  # noqa: E402
    ALL_COMMENT_STOPWORDS,
    COMMENT_IDENTIFIER_PATTERN,
    COMMENT_LINE_PREFIX,
    PYTHON_FILE_SUFFIX,
    STALE_COMMENT_ADDITIONAL_CONTEXT,
    STALE_COMMENT_DENY_TEMPLATE,
    STALE_COMMENT_SYSTEM_MESSAGE,
)


def _first_orphaned_identifier(
    overlying_comment: str,
    all_old_block_lines: list[str],
    all_new_block_lines: list[str],
) -> str | None:
    """Return the first comment identifier the edit removes from the block.

    Args:
        overlying_comment: The stripped standalone comment text above the block.
        all_old_block_lines: The replaced lines as they read before the edit.
        all_new_block_lines: The replacement lines as they read after the edit.

    Returns:
        The first identifier the comment names that matches the old block and
        not the new block, or None when the comment stays consistent.
    """
    words_in_comment = overlying_comment.lstrip(COMMENT_LINE_PREFIX).strip()
    original_block_text = "\n".join(all_old_block_lines)
    revised_block_text = "\n".join(all_new_block_lines)
    for each_identifier in COMMENT_IDENTIFIER_PATTERN.findall(words_in_comment):
        if each_identifier.lower() in ALL_COMMENT_STOPWORDS:
            continue
        bounded_pattern = re.compile(
            "(?<![A-Za-z0-9_])" + re.escape(each_identifier) + "(?![A-Za-z0-9_])"
        )
        if bounded_pattern.search(original_block_text) and not bounded_pattern.search(
            revised_block_text
        ):
            return each_identifier
    return None


def _occurrence_start_offsets(
    old_content: str,
    old_string: str,
    is_replace_all: bool,
) -> list[int]:
    """List the character offsets where old_string starts in old_content.

    Walks old_content left to right the same way str.replace does, so the
    offsets line up with the occurrences the edit actually rewrites.

    Args:
        old_content: The file text before the edit.
        old_string: The text the edit replaces.
        is_replace_all: Whether every occurrence is collected, matching the
            Edit tool's replace_all flag, or only the first one.

    Returns:
        The offset of each matching occurrence, in file order.
    """
    all_offsets: list[int] = []
    search_from = 0
    while True:
        found_at = old_content.find(old_string, search_from)
        if found_at == -1:
            return all_offsets
        all_offsets.append(found_at)
        if not is_replace_all:
            return all_offsets
        search_from = found_at + len(old_string)


def _preceding_line_text(old_content: str, occurrence_start: int) -> str | None:
    """Return the stripped line directly above the line an occurrence sits in.

    Args:
        old_content: The file text before the edit.
        occurrence_start: The character offset where the occurrence begins.

    Returns:
        The stripped text of the line above the occurrence's line, or None
        when that line is the first line in the file.
    """
    containing_line_start = old_content.rfind("\n", 0, occurrence_start) + 1
    if containing_line_start == 0:
        return None
    preceding_line_end = containing_line_start - 1
    preceding_line_start = old_content.rfind("\n", 0, preceding_line_end) + 1
    return old_content[preceding_line_start:preceding_line_end].strip()


def _find_stale_comment_reference(
    old_content: str,
    old_string: str,
    new_string: str,
    is_replace_all: bool,
    file_path: str,
) -> str | None:
    """Check each occurrence old_string rewrites for an orphaned comment above it.

    Args:
        old_content: The file text before the edit.
        old_string: The text the edit replaces.
        new_string: The text the edit substitutes in, empty for a straight
            deletion.
        is_replace_all: Whether every occurrence of old_string is checked,
            matching the Edit tool's replace_all flag.
        file_path: The target path, named in the deny reason.

    Returns:
        The deny-reason text for the first occurrence whose kept comment
        names an identifier old_string carries and new_string drops, or None
        when every kept comment stays consistent with the rewritten line.
    """
    all_old_block_lines = old_string.splitlines()
    all_new_block_lines = new_string.splitlines()
    for each_occurrence_start in _occurrence_start_offsets(old_content, old_string, is_replace_all):
        preceding_line = _preceding_line_text(old_content, each_occurrence_start)
        if preceding_line is None or not preceding_line.startswith(COMMENT_LINE_PREFIX):
            continue
        maybe_identifier = _first_orphaned_identifier(
            preceding_line, all_old_block_lines, all_new_block_lines
        )
        if maybe_identifier is not None:
            return STALE_COMMENT_DENY_TEMPLATE.format(
                file_path=file_path,
                contradicted_comment=preceding_line,
                orphaned_name=maybe_identifier,
            )
    return None


def evaluate(payload_by_key: dict[str, object]) -> str | None:
    """Decide whether an Edit payload orphans a comment above a changed line.

    Reads the target file from disk and checks the line directly above each
    occurrence the edit rewrites for a kept standalone comment whose named
    identifier the edit removes from the line below it. Non-Edit tools,
    non-Python targets, unreadable files, and an old_string absent from the
    file all pass.

    Args:
        payload_by_key: The PreToolUse payload with tool_name and tool_input.

    Returns:
        The deny-reason text when the edit is denied, or None when allowed.
    """
    raw_tool_name = payload_by_key.get("tool_name", "")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    if tool_name != EDIT_TOOL_NAME:
        return None

    raw_tool_input = payload_by_key.get("tool_input", {})
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path.endswith(PYTHON_FILE_SUFFIX):
        return None

    raw_old_string = tool_input.get("old_string", "")
    raw_new_string = tool_input.get("new_string", "")
    old_string = raw_old_string if isinstance(raw_old_string, str) else ""
    new_string = raw_new_string if isinstance(raw_new_string, str) else ""
    if not old_string:
        return None

    try:
        old_content = Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if old_string not in old_content:
        return None

    is_replace_all = tool_input.get("replace_all") is True
    return _find_stale_comment_reference(
        old_content, old_string, new_string, is_replace_all, file_path
    )


def build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the full deny payload the hook writes for a deny-reason string.

    Logs the block, then returns the permission decision with the corrective
    guidance in additionalContext, the user-facing systemMessage, and output
    suppression, matching the deny shape the sibling blockers write.

    Args:
        deny_reason: The permissionDecisionReason text for the denial.

    Returns:
        The deny payload dictionary the hook serializes to stdout.
    """
    log_hook_block(
        calling_hook_name="stale_comment_reference_blocker.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
            "additionalContext": STALE_COMMENT_ADDITIONAL_CONTEXT,
        },
        "systemMessage": STALE_COMMENT_SYSTEM_MESSAGE,
        "suppressOutput": True,
    }


def main() -> None:
    """Run the gate over the stdin payload dictionary and emit any denial.
    """
    payload_dictionary = read_hook_input_dictionary_from_stdin()
    if payload_dictionary is None:
        sys.exit(0)

    deny_reason = evaluate(payload_dictionary)
    if deny_reason is None:
        sys.exit(0)

    _emit_deny_line(build_deny_payload(deny_reason), sys.stdout)
    sys.exit(0)


def _emit_deny_line(
    all_deny_payload_fields: dict[str, object], destination_stream: TextIO
) -> None:
    """Write the deny payload JSON as one line to the given stream.

    Args:
        all_deny_payload_fields: The deny payload to serialize.
        destination_stream: The stream the JSON line is written to.
    """
    destination_stream.write(json.dumps(all_deny_payload_fields) + "\n")
    destination_stream.flush()


if __name__ == "__main__":
    main()
