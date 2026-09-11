#!/usr/bin/env python3
"""PostToolUse hook that blocks Write/Edit when the file holds CR or NUL bytes."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.post_tool_use_dispatcher_constants import (  # noqa: E402
    BLOCK_DECISION,
    DECISION_KEY,
    REASON_KEY,
)
from hooks_constants.write_byte_hygiene_constants import (  # noqa: E402
    ALLOWED_TOOL_NAMES,
    CARRIAGE_RETURN_BYTE,
    CRLF_ERROR_MESSAGE,
    HYGIENE_EXIT_CODE,
    HygieneStatus,
    NUL_BYTE,
    NUL_ERROR_MESSAGE,
)


def classify_file_bytes(payload: bytes) -> HygieneStatus:
    """Return the first hygiene violation in payload, or ok.

    Carriage return is checked before NUL so a file with both reports CRLF.
    """
    if CARRIAGE_RETURN_BYTE in payload:
        return "crlf"
    if NUL_BYTE in payload:
        return "nul"
    return "ok"


def message_for_status(status: HygieneStatus) -> str:
    """Return the stderr/block reason for a non-ok status."""
    if status == "crlf":
        return CRLF_ERROR_MESSAGE
    if status == "nul":
        return NUL_ERROR_MESSAGE
    raise ValueError(f"no message for status {status!r}")


def _read_hook_input() -> dict[str, object] | None:
    try:
        parsed_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed_input, dict):
        return None
    return parsed_input


def _read_string_field(field_source: Mapping[str, object], field_name: str) -> str:
    field_value = field_source.get(field_name)
    return field_value if isinstance(field_value, str) else ""


def _read_hook_file_path(hook_input: Mapping[str, object]) -> str:
    tool_input = hook_input.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    return _read_string_field(tool_input, "file_path")


def _emit_block(reason_text: str) -> None:
    sys.stderr.write(reason_text + "\n")
    sys.stderr.flush()
    block_payload = {
        DECISION_KEY: BLOCK_DECISION,
        REASON_KEY: reason_text,
    }
    sys.stdout.write(json.dumps(block_payload) + "\n")
    sys.stdout.flush()
    raise SystemExit(HYGIENE_EXIT_CODE)


def main() -> None:
    """Block Write/Edit when the written file contains CR or NUL bytes."""
    hook_input = _read_hook_input()
    if hook_input is None:
        return

    tool_name = _read_string_field(hook_input, "tool_name")
    if tool_name not in ALLOWED_TOOL_NAMES:
        return

    file_path = _read_hook_file_path(hook_input)
    if not file_path:
        return

    target_path = Path(file_path)
    if not target_path.is_file():
        return

    try:
        file_bytes = target_path.read_bytes()
    except OSError:
        return

    status = classify_file_bytes(file_bytes)
    if status == "ok":
        return
    _emit_block(message_for_status(status))


if __name__ == "__main__":
    main()
