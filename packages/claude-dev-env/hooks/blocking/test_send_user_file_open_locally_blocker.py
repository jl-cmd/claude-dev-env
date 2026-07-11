"""Unit tests for the send-user-file-open-locally PreToolUse hook."""

import importlib.util
import io
import json
import pathlib
import sys
from unittest import mock

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "send_user_file_open_locally_blocker",
    _HOOK_DIR / "send_user_file_open_locally_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

_should_block = hook_module._should_block

from hooks_constants.send_user_file_open_locally_blocker_constants import (
    CORRECTIVE_MESSAGE,
    PROACTIVE_STATUS,
    TOOL_NAME,
)


def test_blocks_normal_status() -> None:
    assert _should_block("normal") is True


def test_blocks_empty_status() -> None:
    assert _should_block("") is True


def test_blocks_unknown_status() -> None:
    assert _should_block("whatever") is True


def test_allows_proactive_status() -> None:
    assert _should_block(PROACTIVE_STATUS) is False


def test_corrective_message_points_to_show_asset() -> None:
    assert "Show-Asset.ps1" in CORRECTIVE_MESSAGE


def test_corrective_message_names_proactive_escape_hatch() -> None:
    assert PROACTIVE_STATUS in CORRECTIVE_MESSAGE


def _run_main_with_io(input_text: str) -> str:
    with mock.patch("sys.stdin", io.StringIO(input_text)):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            try:
                hook_module.main()
            except SystemExit:
                pass
            return mock_stdout.getvalue()


def test_main_blocks_normal_attach() -> None:
    hook_input = {
        "tool_name": TOOL_NAME,
        "tool_input": {"files": ["report.html"], "status": "normal"},
    }
    output_text = _run_main_with_io(json.dumps(hook_input))
    output = json.loads(output_text)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Show-Asset.ps1" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_main_allows_proactive_attach() -> None:
    hook_input = {
        "tool_name": TOOL_NAME,
        "tool_input": {"files": ["report.html"], "status": "proactive"},
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_blocks_when_status_missing() -> None:
    hook_input = {
        "tool_name": TOOL_NAME,
        "tool_input": {"files": ["report.html"]},
    }
    output_text = _run_main_with_io(json.dumps(hook_input))
    output = json.loads(output_text)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_blocks_when_tool_input_is_null() -> None:
    hook_input = {
        "tool_name": TOOL_NAME,
        "tool_input": None,
    }
    output_text = _run_main_with_io(json.dumps(hook_input))
    output = json.loads(output_text)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_passes_wrong_tool_name() -> None:
    hook_input = {
        "tool_name": "Write",
        "tool_input": {"files": ["report.html"], "status": "normal"},
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_malformed_json() -> None:
    assert _run_main_with_io("not valid json {{{") == ""
