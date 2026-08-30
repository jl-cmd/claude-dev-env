#!/usr/bin/env python3
"""PreToolUse gate: deny Luna spawns that do not use the fast service tier."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Mapping, TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.luna_fast_mode_gate_constants import (  # noqa: E402
    ALL_SPAWN_TOOL_NAMES,
    CALLING_HOOK_NAME,
    DENY_ADDITIONAL_CONTEXT,
    DENY_PREVIEW_TEMPLATE,
    DENY_REASON,
    FAST_SERVICE_TIER,
    HOOK_EVENT_NAME,
    LUNA_MODEL_ALIAS,
    MAXIMUM_PREVIEW_FIELD_LENGTH,
    MODEL_FIELD_NAME,
    MODEL_SEGMENT_SPLIT_PATTERN,
    SERVICE_TIER_FIELD_NAME,
    TOOL_INPUT_FIELD_NAME,
    TOOL_NAME_FIELD_NAME,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def _model_names_the_luna_tier(model_identifier: str) -> bool:
    """Report whether a model string names the Luna tier.

    Args:
        model_identifier: The spawn's ``model`` string.

    Returns:
        True when a model segment reads ``luna`` in any letter case; False
        for another tier.
    """
    all_segments = MODEL_SEGMENT_SPLIT_PATTERN.split(model_identifier.strip().lower())
    return LUNA_MODEL_ALIAS in all_segments


def _denied_spawn_details(
    all_payload_by_field: Mapping[str, object],
) -> tuple[str, object] | None:
    """Return model and service tier for a Luna spawn that must be denied.

    Args:
        all_payload_by_field: The parsed PreToolUse payload.

    Returns:
        The model and service tier for an invalid Luna spawn; None otherwise.
    """
    if all_payload_by_field.get(TOOL_NAME_FIELD_NAME, "") not in ALL_SPAWN_TOOL_NAMES:
        return None
    tool_input = all_payload_by_field.get(TOOL_INPUT_FIELD_NAME, {})
    if not isinstance(tool_input, dict):
        return None
    model_identifier = tool_input.get(MODEL_FIELD_NAME)
    if not isinstance(model_identifier, str):
        return None
    if not _model_names_the_luna_tier(model_identifier):
        return None
    service_tier = tool_input.get(SERVICE_TIER_FIELD_NAME)
    if service_tier == FAST_SERVICE_TIER:
        return None
    return model_identifier, service_tier


def _build_denial_preview(model_identifier: str, service_tier: object) -> str:
    """Build a bounded preview for the block log without recording the prompt.

    Args:
        model_identifier: The Luna model string.
        service_tier: The supplied service tier value.

    Returns:
        A bounded preview naming only the model and service tier fields.
    """
    model_text = model_identifier[:MAXIMUM_PREVIEW_FIELD_LENGTH]
    service_tier_text = str(service_tier)[:MAXIMUM_PREVIEW_FIELD_LENGTH]
    return DENY_PREVIEW_TEMPLATE.format(
        model_text=model_text,
        service_tier_text=service_tier_text,
    )


def _emit_denial(
    decision_stream: TextIO,
    all_payload_by_field: Mapping[str, object],
    model_identifier: str,
    service_tier: object,
) -> None:
    """Log the denied spawn and write the PreToolUse deny payload.

    Args:
        decision_stream: Writable stream for the JSON decision.
        all_payload_by_field: The parsed PreToolUse payload.
        model_identifier: The denied Luna model string.
        service_tier: The invalid service tier value.
    """
    denial = {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": "deny",
            "permissionDecisionReason": DENY_REASON,
            "additionalContext": DENY_ADDITIONAL_CONTEXT,
        }
    }
    log_hook_block(
        calling_hook_name=CALLING_HOOK_NAME,
        hook_event=HOOK_EVENT_NAME,
        block_reason=DENY_REASON,
        tool_name=str(all_payload_by_field.get(TOOL_NAME_FIELD_NAME, "")),
        offending_input_preview=_build_denial_preview(model_identifier, service_tier),
    )
    decision_stream.write(json.dumps(denial) + "\n")
    decision_stream.flush()


def main() -> None:
    """Read the PreToolUse payload and deny an invalid Luna spawn."""
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None:
        sys.exit(0)
    denied_details = _denied_spawn_details(hook_payload)
    if denied_details is None:
        sys.exit(0)
    denied_model, denied_service_tier = denied_details
    _emit_denial(
        sys.stdout,
        hook_payload,
        denied_model,
        denied_service_tier,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
