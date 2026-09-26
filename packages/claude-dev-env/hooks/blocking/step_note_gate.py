#!/usr/bin/env python3
"""PreToolUse hook that asks for a status line before each tool call.

A status line is a short text block, such as "Reading hooks.json.", that
opens the message holding the call. It works like a progress caption so the
user can follow the session.

The gate is off by default. The step-notes skill turns it on by creating the
flag file at STEP_NOTES_ON_FLAG_PATH, and off again by removing it.

Claude Code writes the assistant message to the transcript after this hook
starts: 100 to 420 ms later in headless runs, and 650 ms to past 3 s in the
desktop app. The hook polls the transcript tail until its own tool_use entry
appears. Three cases pass without a check:

- A subagent call. Its input carries agent_id, its messages live in a separate
  transcript, and its status lines stay inside the subagent.
- A call that does not appear before the poll limit.
- A call whose message is larger than the tail window the hook reads.
"""

from __future__ import annotations

import enum
import json
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

hooks_root_directory = str(Path(__file__).resolve().parent.parent)
if hooks_root_directory not in sys.path:
    sys.path.insert(0, hooks_root_directory)

from hooks_constants.step_note_gate_constants import (
    ALLOW_EXIT_CODE,
    ASSISTANT_ROLE,
    BLOCK_EXIT_CODE,
    BLOCK_MESSAGE,
    POLL_INTERVAL_SECONDS,
    POLL_LIMIT_SECONDS,
    STEP_NOTES_ON_FLAG_PATH,
    TAIL_WINDOW_BYTES,
    TEXT_BLOCK_TYPE,
    TOOL_USE_BLOCK_TYPE,
    USER_ROLE,
)


class NoteCheck(enum.Enum):
    NOTED = "noted"
    MISSING = "missing"
    CALL_NOT_WRITTEN = "call_not_written"
    WINDOW_TOO_SHORT = "window_too_short"


def read_transcript_tail(transcript_path: Path) -> list[dict]:
    """Parse the complete JSON lines in the last TAIL_WINDOW_BYTES of the transcript."""
    try:
        with transcript_path.open("rb") as transcript_file:
            file_size = transcript_file.seek(0, os.SEEK_END)
            window_start = max(0, file_size - TAIL_WINDOW_BYTES)
            transcript_file.seek(window_start)
            window_bytes = transcript_file.read()
    except OSError:
        return []
    window_lines = window_bytes.split(b"\n")
    if window_start > 0:
        window_lines = window_lines[1:]
    all_entries = []
    for each_line in window_lines:
        try:
            parsed_entry = json.loads(each_line)
        except ValueError:
            continue
        if isinstance(parsed_entry, dict):
            all_entries.append(parsed_entry)
    return all_entries


def entry_content_blocks(entry: dict) -> list[dict]:
    """Return the content blocks of one transcript entry, wrapping plain text as a text block."""
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": TEXT_BLOCK_TYPE, "text": content}]
    if isinstance(content, list):
        return [each_block for each_block in content if isinstance(each_block, dict)]
    return []


def transcript_blocks(all_entries: list[dict]) -> Iterator[tuple[str, dict]]:
    """Yield (role, content block) pairs for user and assistant entries, in order."""
    for each_entry in all_entries:
        role = each_entry.get("type")
        if role not in (USER_ROLE, ASSISTANT_ROLE):
            continue
        for each_block in entry_content_blocks(each_entry):
            yield role, each_block


def is_step_note(block: dict) -> bool:
    return block.get("type") == TEXT_BLOCK_TYPE and bool(str(block.get("text", "")).strip())


def check_step_note(all_entries: list[dict], tool_use_id: str) -> NoteCheck:
    """Report whether a text block sits between the last user entry and this call.

    A user entry is either a tool result or a prompt, so it marks where the
    previous step ended. Sibling calls in one message share the note that
    opens the message.
    """
    all_blocks = list(transcript_blocks(all_entries))
    call_position = next(
        (
            position
            for position, (role, block) in enumerate(all_blocks)
            if role == ASSISTANT_ROLE
            and block.get("type") == TOOL_USE_BLOCK_TYPE
            and block.get("id") == tool_use_id
        ),
        None,
    )
    if call_position is None:
        return NoteCheck.CALL_NOT_WRITTEN
    for each_preceding_role, each_preceding_block in reversed(all_blocks[:call_position]):
        if each_preceding_role == USER_ROLE:
            return NoteCheck.MISSING
        if is_step_note(each_preceding_block):
            return NoteCheck.NOTED
    return NoteCheck.WINDOW_TOO_SHORT


def wait_for_note_check(transcript_path: Path, tool_use_id: str) -> NoteCheck:
    deadline = time.monotonic() + POLL_LIMIT_SECONDS
    while True:
        note_check = check_step_note(read_transcript_tail(transcript_path), tool_use_id)
        if note_check is not NoteCheck.CALL_NOT_WRITTEN or time.monotonic() >= deadline:
            return note_check
        time.sleep(POLL_INTERVAL_SECONDS)


def main() -> int:
    if not STEP_NOTES_ON_FLAG_PATH.exists():
        return ALLOW_EXIT_CODE
    hook_input = json.load(sys.stdin)
    if hook_input.get("agent_id"):
        return ALLOW_EXIT_CODE
    tool_use_id = hook_input.get("tool_use_id")
    transcript_path = hook_input.get("transcript_path")
    if not tool_use_id or not transcript_path:
        return ALLOW_EXIT_CODE
    if wait_for_note_check(Path(transcript_path), tool_use_id) is NoteCheck.MISSING:
        sys.stderr.write(BLOCK_MESSAGE)
        return BLOCK_EXIT_CODE
    return ALLOW_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
