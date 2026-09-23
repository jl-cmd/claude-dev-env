#!/usr/bin/env python3
"""Hook that keeps poteto-mode loaded in every session, subagent and workflow helper.

::

    Agent or Codex spawn_agent, skill not named -> prompt opens with "invoke pstack:poteto-mode"
    Workflow script helper starts               -> "invoke pstack:poteto-mode now"
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
    SUBAGENT_START_EVENT_NAME,
    ALL_SPAWN_PROMPT_FIELDS_AND_PREFIXES_BY_TOOL_NAME,
    TOOL_USE_BLOCK_TYPE,
    USER_ENTRY_TYPE,
    USER_PROMPT_SUBMIT_EVENT_NAME,
    WORKFLOW_SUBAGENT_TYPE,
)
from hooks_constants.pre_tool_use_allow_output import write_pre_tool_use_allow_to_stdout
from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin
from hooks_constants.setup_project_paths_constants import DECODE_ERRORS_POLICY, UTF8_ENCODING


def subagent_input_with_poteto_mode(
    tool_name: str,
    all_tool_input_fields: dict[str, object],
) -> dict[str, object] | None:
    """Return the spawn input with the poteto-mode invocation first, or None to leave it.

    ::

        Agent        {"prompt": "Reply leaf."}   -> {"prompt": "Before any ...\\n\\nReply leaf."}
        spawn_agent  {"message": "Fix it."}      -> {"message": "$pstack:poteto-mode\\n\\nFix it."}
        Agent        {"prompt": "Invoke pstack:poteto-mode, then ..."}  -> None
        Agent        {"subagent_type": "pstack:poteto-agent", ...}      -> None, it loads the skill

    Claude Code spawns through Agent or Task and Codex through spawn_agent, so
    each tool name carries its own prompt field and invocation text.

    Args:
        tool_name: The spawn tool the session called.
        all_tool_input_fields: The spawn input the session is about to send.
    """
    field_name, invocation_prefix = ALL_SPAWN_PROMPT_FIELDS_AND_PREFIXES_BY_TOOL_NAME[tool_name]
    prompt = all_tool_input_fields.get(field_name)
    if not isinstance(prompt, str) or POTETO_MODE_SKILL_NAME in prompt:
        return None
    if all_tool_input_fields.get("subagent_type") in ALL_SELF_LOADING_SUBAGENT_TYPES:
        return None
    return {**all_tool_input_fields, field_name: invocation_prefix + PROMPT_SEPARATOR + prompt}


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
        SubagentStart, workflow-subagent                 -> NOT_LOADED_REMINDER
        UserPromptSubmit, transcript lacks the skill     -> NOT_LOADED_REMINDER
        UserPromptSubmit, transcript loaded the skill    -> None

    Args:
        all_hook_fields: The parsed hook input.
    """
    event_name = all_hook_fields.get("hook_event_name")
    if event_name == SESSION_START_EVENT_NAME:
        return COMPACTION_REMINDER if all_hook_fields.get("source") == COMPACTION_SOURCE else None
    if event_name == SUBAGENT_START_EVENT_NAME:
        is_workflow_helper = all_hook_fields.get("agent_type") == WORKFLOW_SUBAGENT_TYPE
        return NOT_LOADED_REMINDER if is_workflow_helper else None
    if event_name != USER_PROMPT_SUBMIT_EVENT_NAME:
        return None
    if _is_loaded_in_transcript(all_hook_fields.get("transcript_path")):
        return None
    return NOT_LOADED_REMINDER


def _is_subagent_spawn(all_hook_fields: dict[str, object]) -> bool:
    return (
        all_hook_fields.get("hook_event_name") == PRE_TOOL_USE_EVENT_NAME
        and all_hook_fields.get("tool_name") in ALL_SPAWN_PROMPT_FIELDS_AND_PREFIXES_BY_TOOL_NAME
        and isinstance(all_hook_fields.get("tool_input"), dict)
    )


def main() -> None:
    """Rewrite a subagent prompt, or print the reminder its event needs, or stay quiet."""
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None:
        return
    if _is_subagent_spawn(hook_payload):
        rewritten_input = subagent_input_with_poteto_mode(
            hook_payload["tool_name"], hook_payload["tool_input"]
        )
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
