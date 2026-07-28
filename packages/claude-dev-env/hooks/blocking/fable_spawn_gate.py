#!/usr/bin/env python3
"""PreToolUse gate: deny a fable-tier subagent spawn that carries no marker.

One exact token in the spawn prompt authorizes a spawn at the fable tier::

    model: fable,           no FABLE-SPAWN-AUTHORIZED   flag: deny
    model: claude-fable-5,  no FABLE-SPAWN-AUTHORIZED   flag: deny
    model: fable,           FABLE-SPAWN-AUTHORIZED      ok:   allow
    model: claude-sonnet-4, prompt either way           ok:   allow
    no model field,         prompt either way           ok:   allow

The gate reads an ``Agent`` or ``Task`` call and finds the tier in the model
field whether that field carries the bare alias or a full model id, in any
letter case. Its deny reason names the token and the advisor-protocol
document that holds the bind rule.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Mapping, TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.fable_spawn_gate_constants import (  # noqa: E402
    ALL_SPAWN_TOOL_NAMES,
    CALLING_HOOK_NAME,
    DENY_REASON,
    FABLE_MODEL_ALIAS,
    FABLE_SPAWN_AUTHORIZATION_MARKER,
    HOOK_EVENT_NAME,
    MODEL_FIELD_NAME,
    MODEL_SEGMENT_SPLIT_PATTERN,
    PROMPT_FIELD_NAME,
    TOOL_INPUT_FIELD_NAME,
    TOOL_NAME_FIELD_NAME,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def _spawn_model_is_fable(all_tool_input: Mapping[str, object]) -> bool:
    """Report whether the spawn's model field names the fable tier.

    The field carries either the bare alias or a full model id, so the
    lowercased string is cut on its delimiters and the tier is looked for as
    a whole segment::

        fable            -> ['fable']                 flag: fable tier
        claude-fable-5   -> ['claude', 'fable', '5']  flag: fable tier
        claude-sonnet-4  -> ['claude', 'sonnet', '4'] ok:   another tier
        affable          -> ['affable']               ok:   another tier

    Args:
        all_tool_input: The spawn's ``tool_input`` mapping.

    Returns:
        True when a model segment reads ``fable`` in any letter case; False
        for another tier and for an absent or non-string field.
    """
    model_identifier = all_tool_input.get(MODEL_FIELD_NAME)
    if not isinstance(model_identifier, str):
        return False
    all_segments = MODEL_SEGMENT_SPLIT_PATTERN.split(model_identifier.strip().lower())
    return FABLE_MODEL_ALIAS in all_segments


def _prompt_carries_authorization_marker(all_tool_input: Mapping[str, object]) -> bool:
    """Report whether the spawn prompt holds the exact authorization token.

    Args:
        all_tool_input: The spawn's ``tool_input`` mapping.

    Returns:
        True when the prompt is a string holding the marker token; False for
        an unmarked prompt and for an absent or non-string field.
    """
    spawn_prompt = all_tool_input.get(PROMPT_FIELD_NAME)
    if not isinstance(spawn_prompt, str):
        return False
    return FABLE_SPAWN_AUTHORIZATION_MARKER in spawn_prompt


def _should_block(all_payload_by_field: Mapping[str, object]) -> bool:
    """Decide whether this tool call is an unauthorized fable spawn.

    Args:
        all_payload_by_field: The parsed PreToolUse payload, keyed by
            top-level field name.

    Returns:
        True only for a spawn tool call at the fable tier whose prompt lacks
        the authorization marker.
    """
    if all_payload_by_field.get(TOOL_NAME_FIELD_NAME, "") not in ALL_SPAWN_TOOL_NAMES:
        return False
    tool_input = all_payload_by_field.get(TOOL_INPUT_FIELD_NAME, {})
    if not isinstance(tool_input, dict):
        return False
    if not _spawn_model_is_fable(tool_input):
        return False
    return not _prompt_carries_authorization_marker(tool_input)


def _emit_denial(
    decision_stream: TextIO,
    all_payload_by_field: Mapping[str, object],
) -> None:
    """Log the denied spawn and write the PreToolUse deny payload.

    Args:
        decision_stream: Writable text stream — production code passes
            ``sys.stdout``; tests pass a ``StringIO`` to capture the JSON.
        all_payload_by_field: The parsed PreToolUse payload, whose tool name
            and spawn input name the denied spawn in the hook-blocks log.
    """
    denial = {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": "deny",
            "permissionDecisionReason": DENY_REASON,
        }
    }
    log_hook_block(
        calling_hook_name=CALLING_HOOK_NAME,
        hook_event=HOOK_EVENT_NAME,
        block_reason=DENY_REASON,
        tool_name=str(all_payload_by_field.get(TOOL_NAME_FIELD_NAME, "")),
        offending_input_preview=str(all_payload_by_field.get(TOOL_INPUT_FIELD_NAME, {})),
    )
    decision_stream.write(json.dumps(denial) + "\n")
    decision_stream.flush()


def main() -> None:
    """Read the PreToolUse payload and deny an unmarked fable spawn."""
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None:
        sys.exit(0)
    if not _should_block(hook_payload):
        sys.exit(0)
    _emit_denial(sys.stdout, hook_payload)
    sys.exit(0)


if __name__ == "__main__":
    main()
