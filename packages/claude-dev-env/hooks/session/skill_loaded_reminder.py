#!/usr/bin/env python3
"""PreToolUse, SessionStart and UserPromptSubmit hook. Keeps poteto-mode loaded in every context.

::

    Agent tool call, prompt lacks the skill      -> prompt opens with "invoke pstack:poteto-mode"
    context compacted mid-run                    -> "invoke pstack:poteto-mode again"
    user turn, skill not loaded since compacting -> "invoke pstack:poteto-mode now"
    user turn, skill already loaded              -> nothing

A session that loaded the skill hears nothing more until a compaction drops it.
The hook prints its output and stops.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.skill_loaded_reminder_constants import (
    ALL_SELF_LOADING_SUBAGENT_TYPES,
    ALL_SUBAGENT_TOOL_NAMES,
    ASSISTANT_ENTRY_TYPE,
    COMPACT_BOUNDARY_SUBTYPE,
    COMPACTION_REMINDER,
    COMPACTION_SOURCE,
    NOT_LOADED_REMINDER,
    POTETO_MODE_SKILL_NAME,
    PRE_TOOL_USE_EVENT_NAME,
    PROMPT_SEPARATOR,
    SESSION_START_EVENT_NAME,
    SKILL_TOOL_NAME,
    SLASH_COMMAND_MARKER,
    SUBAGENT_PROMPT_PREFIX,
    TOOL_USE_BLOCK_TYPE,
    USER_ENTRY_TYPE,
    USER_PROMPT_SUBMIT_EVENT_NAME,
)
from hooks_constants.pre_tool_use_allow_output import write_pre_tool_use_allow_to_stdout
from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin
from hooks_constants.setup_project_paths_constants import DECODE_ERRORS_POLICY, UTF8_ENCODING


def subagent_input_with_poteto_mode(
    all_tool_input_fields: dict[str, object],
) -> dict[str, object] | None:
    """Return the Agent tool input with the poteto-mode instruction first, or None to leave it.

    ::

        {"prompt": "Reply leaf."}                          -> {"prompt": "Before any ...\\n\\nReply leaf."}
        {"prompt": "Invoke pstack:poteto-mode, then ..."}  -> None
        {"subagent_type": "pstack:poteto-agent", ...}      -> None, that agent loads the skill itself

    Args:
        all_tool_input_fields: The Agent tool input the session is about to send.
    """
    prompt = all_tool_input_fields.get("prompt")
    if not isinstance(prompt, str) or POTETO_MODE_SKILL_NAME in prompt:
        return None
    if all_tool_input_fields.get("subagent_type") in ALL_SELF_LOADING_SUBAGENT_TYPES:
        return None
    return {**all_tool_input_fields, "prompt": SUBAGENT_PROMPT_PREFIX + PROMPT_SEPARATOR + prompt}


def _invokes_poteto_mode(all_entry_fields: dict[str, object]) -> bool:
    message = all_entry_fields.get("message")
    if not isinstance(message, dict):
        return False
    content_blocks = message.get("content")
    if all_entry_fields.get("type") == USER_ENTRY_TYPE and isinstance(content_blocks, str):
        return SLASH_COMMAND_MARKER in content_blocks
    if all_entry_fields.get("type") != ASSISTANT_ENTRY_TYPE or not isinstance(content_blocks, list):
        return False
    return any(
        isinstance(each_block, dict)
        and each_block.get("type") == TOOL_USE_BLOCK_TYPE
        and each_block.get("name") == SKILL_TOOL_NAME
        and isinstance(each_block.get("input"), dict)
        and each_block["input"].get("skill") == POTETO_MODE_SKILL_NAME
        for each_block in content_blocks
    )


def _marker_entry(transcript_line: str) -> dict[str, object] | None:
    if (
        COMPACT_BOUNDARY_SUBTYPE not in transcript_line
        and POTETO_MODE_SKILL_NAME not in transcript_line
    ):
        return None
    try:
        parsed_entry = json.loads(transcript_line)
    except json.JSONDecodeError:
        return None
    return parsed_entry if isinstance(parsed_entry, dict) else None


def _is_loaded_after(all_entry_fields: dict[str, object], was_loaded: bool) -> bool:
    if all_entry_fields.get("subtype") == COMPACT_BOUNDARY_SUBTYPE:
        return False
    return was_loaded or _invokes_poteto_mode(all_entry_fields)


def is_poteto_mode_loaded(all_transcript_lines: Iterable[str]) -> bool:
    """Return True when the transcript invoked the skill after its last compaction.

    ::

        Skill(pstack:poteto-mode) ... Read ... Edit               -> True
        /pstack:poteto-mode typed as a command ... Read           -> True
        Skill(pstack:poteto-mode) ... compact_boundary ... Read   -> False
        Read ... Edit                                             -> False

    Only lines naming the skill or a compaction are parsed, so a long transcript
    reads fast.

    Args:
        all_transcript_lines: The session transcript, one JSON entry per line.
    """
    is_loaded = False
    for each_line in all_transcript_lines:
        all_entry_fields = _marker_entry(each_line)
        if all_entry_fields is not None:
            is_loaded = _is_loaded_after(all_entry_fields, is_loaded)
    return is_loaded


def _is_loaded_in_transcript(transcript_path: object) -> bool:
    if not isinstance(transcript_path, str):
        return False
    try:
        with open(
            transcript_path, encoding=UTF8_ENCODING, errors=DECODE_ERRORS_POLICY
        ) as transcript:
            return is_poteto_mode_loaded(transcript)
    except OSError:
        return False


def reminder_for(all_hook_fields: dict[str, object]) -> str | None:
    """Return the reminder a session event carries, or None when the skill is in view.

    ::

        SessionStart, source compact                     -> COMPACTION_REMINDER
        UserPromptSubmit, transcript lacks the skill     -> NOT_LOADED_REMINDER
        UserPromptSubmit, transcript loaded the skill    -> None

    Args:
        all_hook_fields: The parsed hook input.
    """
    event_name = all_hook_fields.get("hook_event_name")
    if event_name == SESSION_START_EVENT_NAME:
        return COMPACTION_REMINDER if all_hook_fields.get("source") == COMPACTION_SOURCE else None
    if event_name != USER_PROMPT_SUBMIT_EVENT_NAME:
        return None
    if _is_loaded_in_transcript(all_hook_fields.get("transcript_path")):
        return None
    return NOT_LOADED_REMINDER


def _is_subagent_spawn(all_hook_fields: dict[str, object]) -> bool:
    return (
        all_hook_fields.get("hook_event_name") == PRE_TOOL_USE_EVENT_NAME
        and all_hook_fields.get("tool_name") in ALL_SUBAGENT_TOOL_NAMES
        and isinstance(all_hook_fields.get("tool_input"), dict)
    )


def main() -> None:
    """Rewrite a subagent prompt, or print the reminder its event needs, or stay quiet."""
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None:
        return
    if _is_subagent_spawn(hook_payload):
        rewritten_input = subagent_input_with_poteto_mode(hook_payload["tool_input"])
        if rewritten_input is not None:
            write_pre_tool_use_allow_to_stdout(rewritten_input)
        return
    reminder = reminder_for(hook_payload)
    if reminder is None:
        return
    reminder_output = {
        "hookSpecificOutput": {
            "hookEventName": hook_payload["hook_event_name"],
            "additionalContext": reminder,
        }
    }
    sys.stdout.write(json.dumps(reminder_output) + "\n")


if __name__ == "__main__":
    main()
