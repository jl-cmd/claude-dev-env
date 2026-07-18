"""Shared deny scaffold for the code-review PreToolUse gates.

The push gate and the PR-create gate deny a blocked tool call the same way: a
``hookSpecificOutput`` payload carrying the deny decision and a corrective
reason, logged through ``log_hook_block`` before it reaches stdout. This module
holds that one payload builder and the log-and-emit helper, so the two gates
share a single deny shape and stay in step.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    _blocking_directory = str(Path(__file__).resolve().parent)
    _hooks_directory = str(Path(__file__).resolve().parent.parent)
    for each_bootstrap_directory in (_blocking_directory, _hooks_directory):
        if each_bootstrap_directory not in sys.path:
            sys.path.insert(0, each_bootstrap_directory)

    from code_review_enforcement_config_bootstrap import (
        register_code_review_enforcement_constants,
    )

    register_code_review_enforcement_constants()

    from config.code_review_enforcement_constants import (
        DENY_PERMISSION_DECISION,
        PRE_TOOL_USE_HOOK_EVENT_NAME,
    )

    from hooks_constants.hook_block_logger import log_hook_block
except ImportError as import_error:
    raise ImportError(
        "the code_review_gate_deny dependencies did not import; "
        "ensure the hooks directory is importable."
    ) from import_error


def build_code_review_deny_payload(deny_reason: str) -> dict[str, dict[str, str]]:
    """Build the PreToolUse deny payload for a blocked code-review gate action.

    Args:
        deny_reason: The corrective message naming why the action is denied.

    Returns:
        The ``hookSpecificOutput`` deny payload.
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": PRE_TOOL_USE_HOOK_EVENT_NAME,
            "permissionDecision": DENY_PERMISSION_DECISION,
            "permissionDecisionReason": deny_reason,
        }
    }


def log_and_emit_code_review_deny(deny_reason: str, tool_name: str, hook_module_name: str) -> None:
    """Log a code-review gate block and write its deny payload to stdout.

    Args:
        deny_reason: The corrective message naming why the action is denied.
        tool_name: The name of the gated tool, recorded in the block log.
        hook_module_name: The calling gate's module name, recorded in the log.
    """
    log_hook_block(
        calling_hook_name=hook_module_name,
        hook_event=PRE_TOOL_USE_HOOK_EVENT_NAME,
        block_reason=deny_reason,
        tool_name=tool_name if isinstance(tool_name, str) else None,
    )
    sys.stdout.write(json.dumps(build_code_review_deny_payload(deny_reason)) + "\n")
