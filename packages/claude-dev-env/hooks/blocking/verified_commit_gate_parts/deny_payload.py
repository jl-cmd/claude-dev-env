"""Build the PreToolUse deny payload the verified-commit gate emits.

::

    deny_reason = "BLOCKED: needs a verdict"
    build_deny_payload(deny_reason)["hookSpecificOutput"]["permissionDecision"]
    -> "deny"

The payload carries the deny decision and reason next to
``VERIFY_SKIP_ADDITIONAL_CONTEXT``, so the blocked agent learns at the moment
of the block when the ``# verify-skip`` marker is legitimate.
"""

from __future__ import annotations

from typing import TypedDict

from config.verified_commit_context_constants import VERIFY_SKIP_ADDITIONAL_CONTEXT
from config.verified_commit_gate_output_constants import (
    DENY_PERMISSION_DECISION,
    PRE_TOOL_USE_HOOK_EVENT_NAME,
)


class _HookSpecificOutput(TypedDict):
    hookEventName: str
    permissionDecision: str
    permissionDecisionReason: str
    additionalContext: str


class DenyPayload(TypedDict):
    hookSpecificOutput: _HookSpecificOutput


def build_deny_payload(deny_reason: str) -> DenyPayload:
    """Build the PreToolUse deny payload for a blocked commit/push.

    Args:
        deny_reason: The corrective message naming why the command is denied.

    Returns:
        The ``hookSpecificOutput`` deny payload, including the verify-skip
        additional context.
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": PRE_TOOL_USE_HOOK_EVENT_NAME,
            "permissionDecision": DENY_PERMISSION_DECISION,
            "permissionDecisionReason": deny_reason,
            "additionalContext": VERIFY_SKIP_ADDITIONAL_CONTEXT,
        }
    }
