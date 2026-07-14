"""Build, record, and emit the CLAUDE.md orphan-file blocker's deny decision.

The deny reason lists each missing file and closes with the retry hint telling
the author to create the file now, since this row has been recorded.
"""

import json
import sys
from typing import TextIO

from claude_md_orphan_file_blocker_parts.config.orphan_blocker_constants import (
    MISSING_NAME_JOIN_SEPARATOR,
    ROW_FIRST_RETRY_HINT,
)

from hooks_constants.claude_md_orphan_file_blocker_constants import (
    ORPHAN_FILE_ADDITIONAL_CONTEXT,
    ORPHAN_FILE_MESSAGE_TEMPLATE,
    ORPHAN_FILE_SYSTEM_MESSAGE,
)
from hooks_constants.hook_block_logger import log_hook_block


def deny_orphan_files(
    tool_name: str, file_path: str, directory: str, all_missing_filenames: list[str]
) -> None:
    """Build, record, and emit the deny decision listing the missing files.

    Args:
        tool_name: The intercepted tool name, for the block log record.
        file_path: The destination path of the CLAUDE.md.
        directory: The resolved CLAUDE.md directory.
        all_missing_filenames: The referenced filenames absent from the subtree.
    """
    block_payload = build_block_payload(all_missing_filenames, directory)
    log_hook_block(
        calling_hook_name="claude_md_orphan_file_blocker.py",
        hook_event="PreToolUse",
        block_reason=block_payload["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name=tool_name,
        offending_input_preview=file_path,
    )
    emit_hook_result(block_payload, sys.stdout)


def build_block_payload(all_missing_filenames: list[str], directory: str) -> dict:
    """Build the PreToolUse deny payload listing each missing filename.

    Args:
        all_missing_filenames: The referenced filenames absent from the subtree.
        directory: The directory that holds the target CLAUDE.md.

    Returns:
        The hook-result dictionary the harness reads to deny the write, whose
        reason closes with the retry hint.
    """
    formatted_missing = MISSING_NAME_JOIN_SEPARATOR.join(
        f"`{each_name}`" for each_name in all_missing_filenames
    )
    reason = ORPHAN_FILE_MESSAGE_TEMPLATE.format(directory=directory, missing=formatted_missing)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason + ROW_FIRST_RETRY_HINT,
            "additionalContext": ORPHAN_FILE_ADDITIONAL_CONTEXT,
        },
        "systemMessage": ORPHAN_FILE_SYSTEM_MESSAGE,
        "suppressOutput": True,
    }


def emit_hook_result(all_hook_data: dict, output_stream: TextIO) -> None:
    """Write the hook result JSON to the given output stream.

    Args:
        all_hook_data: The hook-result dictionary to serialize.
        output_stream: The stream the harness reads the decision from.
    """
    output_stream.write(json.dumps(all_hook_data) + "\n")
    output_stream.flush()
