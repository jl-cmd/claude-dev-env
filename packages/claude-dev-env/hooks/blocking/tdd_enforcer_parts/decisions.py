"""Build and emit the gate's allow and deny decisions.

Writes the PreToolUse decision JSON to stdout and, on a deny, records the block
and attaches the short user-facing notice.
"""

import json
import sys
from pathlib import Path

from tdd_enforcer_parts.config.tdd_enforcer_constants import (
    FRESHNESS_WINDOW_SECONDS,
    NEWLINE_JOIN_SEPARATOR,
)

from hooks_constants.hook_block_logger import log_hook_block
from hooks_constants.messages import USER_FACING_TDD_NOTICE


def build_deny_reason(production_path: Path, all_candidates: list[Path]) -> str:
    """Return the verbose deny message naming the candidate test files.

    Args:
        production_path: The production file the write targets.
        all_candidates: Candidate test paths the gate looked for.

    Returns:
        The multi-line reason shown when no fresh test satisfies the gate.
    """
    candidate_lines = NEWLINE_JOIN_SEPARATOR.join(f"  - {each_path}" for each_path in all_candidates)
    hook_source_path = Path(__file__).resolve()
    return (
        f"[TDD] Blocking write to production file: {production_path}\n"
        f"No matching test file exists, or it has not been modified within the last "
        f"{FRESHNESS_WINDOW_SECONDS} seconds.\n"
        f"Expected one of:\n{candidate_lines}\n"
        f"Write a failing test first (RED), then the minimum code to pass it (GREEN).\n\n"
        f"If this file legitimately does not need a test (for example, a module containing only "
        f"module-level constants with no behavior), that is a hook enhancement, not a bypass. "
        f"Propose an exemption rule in {hook_source_path} so every similar file benefits "
        f"automatically. Do not add escape-hatch markers to production files."
    )


def emit_allow() -> None:
    """Write the allow decision to stdout."""
    allow_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }
    sys.stdout.write(json.dumps(allow_payload))


def emit_deny(reason: str) -> None:
    """Write the deny decision to stdout and record the block.

    Args:
        reason: The verbose deny reason shown to the agent.
    """
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
        "suppressOutput": True,
        "systemMessage": USER_FACING_TDD_NOTICE,
    }
    log_hook_block(
        calling_hook_name="tdd_enforcer.py",
        hook_event="PreToolUse",
        block_reason=reason,
    )
    sys.stdout.write(json.dumps(deny_payload))
