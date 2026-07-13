"""Build, record, and emit the package-inventory blocker's deny decision.

The deny reason names the omitted file and closes with the retry hint that tells
the author to add the inventory row now, since this write has been recorded.
"""

import json
import os
import sys
from pathlib import Path
from typing import TextIO

from package_inventory_stale_blocker_parts.config.inventory_blocker_constants import (
    FILE_FIRST_RETRY_HINT,
    INVENTORY_NAME_JOIN_SEPARATOR,
)
from package_inventory_stale_blocker_parts.inventory_detection import _InventorySurvey

from hooks_constants.hook_block_logger import log_hook_block
from hooks_constants.package_inventory_stale_blocker_constants import (
    STALE_INVENTORY_ADDITIONAL_CONTEXT,
    STALE_INVENTORY_MESSAGE_TEMPLATE,
    STALE_INVENTORY_SYSTEM_MESSAGE,
)


def deny_stale_inventory(file_path: str, survey: _InventorySurvey) -> None:
    """Build, record, and emit the deny decision for a stale-inventory omission.

    Args:
        file_path: The destination path of the denied new file.
        survey: The maintained-inventory survey the file is absent from.
    """
    block_payload = build_block_payload(file_path, survey)
    log_hook_block(
        calling_hook_name="package_inventory_stale_blocker.py",
        hook_event="PreToolUse",
        block_reason=block_payload["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name="Write",
        offending_input_preview=file_path,
    )
    emit_hook_result(block_payload, sys.stdout)


def build_block_payload(file_path: str, survey: _InventorySurvey) -> dict:
    """Build the PreToolUse deny payload for a stale-inventory omission.

    Args:
        file_path: The destination path of the write.
        survey: The maintained-inventory survey the file is absent from.

    Returns:
        The hook-result dictionary the harness reads to deny the write, whose
        reason closes with the retry hint.
    """
    package_directory = str(Path(file_path).resolve().parent)
    formatted_inventories = INVENTORY_NAME_JOIN_SEPARATOR.join(survey.present_inventory_names)
    reason = STALE_INVENTORY_MESSAGE_TEMPLATE.format(
        filename=os.path.basename(file_path),
        directory=package_directory,
        inventories=formatted_inventories,
        entry_count=len(survey.named_basenames),
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason + FILE_FIRST_RETRY_HINT,
            "additionalContext": STALE_INVENTORY_ADDITIONAL_CONTEXT,
        },
        "systemMessage": STALE_INVENTORY_SYSTEM_MESSAGE,
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
