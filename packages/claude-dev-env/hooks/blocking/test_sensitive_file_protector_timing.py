"""Timing checks for the production PreToolUse dispatcher.

The production dispatcher has a 60-second user-visible timeout in ``hooks.json``.
This test uses a 5-second protection-decision budget. The budget keeps a
Write or Edit decision responsive. The registered timeout supplies the
remaining headroom before the hard timeout.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest

BLOCKING_DIRECTORY = Path(__file__).resolve().parent
CLAUDE_DEV_ENV_DIRECTORY = BLOCKING_DIRECTORY.parent.parent
DISPATCHER_SCRIPT_PATH = BLOCKING_DIRECTORY / "pre_tool_use_dispatcher.py"
HOOKS_JSON_PATH = BLOCKING_DIRECTORY.parent / "hooks.json"

WRITE_TOOL_NAME = "Write"
EDIT_TOOL_NAME = "Edit"
DENY_DECISION = "deny"
MAXIMUM_SAFE_DISPATCHER_SECONDS = 5
PLACEHOLDER_TEMPLATE_BODY = "API_TOKEN=your-token-here\n"


def _registered_dispatcher_command_and_timeout(
    hooks_json_path: Path = HOOKS_JSON_PATH,
) -> tuple[list[str], int]:
    hooks_configuration = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    pre_tool_use_registrations = hooks_configuration["hooks"]["PreToolUse"]
    for each_registration in pre_tool_use_registrations:
        matcher_names = set(each_registration["matcher"].split("|"))
        covers_write_and_edit = {WRITE_TOOL_NAME, EDIT_TOOL_NAME} <= matcher_names
        if not covers_write_and_edit:
            continue
        for each_hook in each_registration["hooks"]:
            command_parts = shlex.split(each_hook["command"])
            if "pre_tool_use_dispatcher.py" not in command_parts[-1]:
                continue
            assert command_parts[0] == "python3"
            dispatcher_script_path = Path(
                command_parts[-1].replace(
                    "${CLAUDE_PLUGIN_ROOT}", str(CLAUDE_DEV_ENV_DIRECTORY)
                )
            )
            assert dispatcher_script_path.resolve() == DISPATCHER_SCRIPT_PATH.resolve()
            registered_timeout_seconds = each_hook["timeout"]
            assert isinstance(registered_timeout_seconds, int)
            return [sys.executable, str(dispatcher_script_path)], registered_timeout_seconds
    raise AssertionError(
        "hooks.json must register pre_tool_use_dispatcher.py for Write and Edit"
    )


def _assert_protection_budget_fits(hooks_json_path: Path = HOOKS_JSON_PATH) -> int:
    _, dispatcher_timeout_seconds = _registered_dispatcher_command_and_timeout(
        hooks_json_path
    )
    assert MAXIMUM_SAFE_DISPATCHER_SECONDS < dispatcher_timeout_seconds, (
        f"registered dispatcher timeout {dispatcher_timeout_seconds}s must exceed the "
        f"{MAXIMUM_SAFE_DISPATCHER_SECONDS}s protection-decision budget"
    )
    return dispatcher_timeout_seconds


def _build_sensitive_payload(tool_name: str, file_path: Path) -> dict[str, object]:
    if tool_name == WRITE_TOOL_NAME:
        return {
            "tool_name": tool_name,
            "tool_input": {
                "file_path": str(file_path),
                "content": PLACEHOLDER_TEMPLATE_BODY,
            },
        }
    return {
        "tool_name": tool_name,
        "tool_input": {
            "file_path": str(file_path),
            "old_string": "API_TOKEN=old-token\n",
            "new_string": PLACEHOLDER_TEMPLATE_BODY,
        },
    }


def _run_dispatcher_with_timing(
    payload: dict[str, object],
) -> tuple[subprocess.CompletedProcess[str], float]:
    payload_text = json.dumps(payload)
    dispatcher_command, dispatcher_timeout_seconds = (
        _registered_dispatcher_command_and_timeout()
    )
    started_at = time.monotonic()
    completed_process = subprocess.run(
        dispatcher_command,
        input=payload_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=dispatcher_timeout_seconds,
    )
    elapsed_seconds = time.monotonic() - started_at
    return completed_process, elapsed_seconds


@pytest.mark.parametrize("tool_name", (WRITE_TOOL_NAME, EDIT_TOOL_NAME))
def test_dispatcher_denies_sensitive_target_within_protection_budget(
    tmp_path: Path, tool_name: str
) -> None:
    dispatcher_timeout_seconds = _assert_protection_budget_fits()
    completed_process, elapsed_seconds = _run_dispatcher_with_timing(
        _build_sensitive_payload(tool_name, tmp_path / ".env")
    )

    assert completed_process.returncode == 0, completed_process.stderr
    parsed_payload = json.loads(completed_process.stdout)
    hook_specific_output = parsed_payload["hookSpecificOutput"]
    assert hook_specific_output["permissionDecision"] == DENY_DECISION
    dispatcher_headroom_seconds = (
        dispatcher_timeout_seconds - MAXIMUM_SAFE_DISPATCHER_SECONDS
    )
    assert elapsed_seconds < MAXIMUM_SAFE_DISPATCHER_SECONDS, (
        f"dispatcher took {elapsed_seconds:.2f}s; the 5s protection-decision budget "
        f"keeps Write/Edit responsive and leaves {dispatcher_headroom_seconds}s "
        f"before the registered {dispatcher_timeout_seconds}s hard timeout; "
        f"{MAXIMUM_SAFE_DISPATCHER_SECONDS}s safety boundary"
    )
