"""Behavior tests for the Cursor-vs-Python gate misfire PreToolUse hook."""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import sys
from unittest import mock

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

_HOOKS_DIR = str(_HOOK_DIR.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

hook_spec = importlib.util.spec_from_file_location(
    "cursor_cli_python_misfire_blocker",
    _HOOK_DIR / "cursor_cli_python_misfire_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

is_cursor_python_gate_misfire = hook_module.is_cursor_python_gate_misfire

from hooks_constants.cursor_cli_python_misfire_blocker_constants import (  # noqa: E402
    CORRECTIVE_MESSAGE,
    DENY_DECISION,
)


def test_blocks_cursor_with_code_rules_gate_and_base_flag() -> None:
    assert (
        is_cursor_python_gate_misfire(
            "cursor code_rules_gate.py --base origin/main"
        )
        is True
    )


def test_blocks_cursor_exe_with_staged_flag_on_python_path() -> None:
    assert (
        is_cursor_python_gate_misfire(r"Cursor.exe C:\temp\helper.py --staged")
        is True
    )


def test_blocks_cursor_cmd_with_repo_root_flag() -> None:
    assert (
        is_cursor_python_gate_misfire("cursor.cmd path/to/module.py --repo-root .")
        is True
    )


def test_allows_code_rules_gate_path_without_extra_flags() -> None:
    assert is_cursor_python_gate_misfire("cursor code_rules_gate.py") is False


def test_allows_cursor_goto_on_python_file() -> None:
    assert is_cursor_python_gate_misfire("cursor -g file.py:10") is False


def test_allows_cursor_goto_on_code_rules_gate_without_gate_flags() -> None:
    assert (
        is_cursor_python_gate_misfire("cursor -g code_rules_gate.py:40") is False
    )


def test_blocks_start_process_cursor_with_quoted_gate_flag() -> None:
    command = (
        r'Start-Process Cursor.exe -ArgumentList '
        r'"C:\temp\helper.py","--staged"'
    )
    assert is_cursor_python_gate_misfire(command) is True


def test_blocks_quoted_full_path_cursor_exe_with_gate_flags() -> None:
    command = (
        r"& 'C:\Program Files\Cursor\Cursor.exe' "
        r"code_rules_gate.py --base origin/main"
    )
    assert is_cursor_python_gate_misfire(command) is True


def test_blocks_unquoted_absolute_cursor_exe_with_gate_flags() -> None:
    command = (
        r"C:\Apps\Cursor\Cursor.exe code_rules_gate.py --base origin/main"
    )
    assert is_cursor_python_gate_misfire(command) is True


def test_allows_relative_path_under_cursor_directory() -> None:
    assert (
        is_cursor_python_gate_misfire(
            r"cursor\fix\x\code_rules_gate.py --base origin/main"
        )
        is False
    )
    assert (
        is_cursor_python_gate_misfire(
            "cursor/fix/x/code_rules_gate.py --base origin/main"
        )
        is False
    )


def test_allows_cursor_open_of_non_python_file() -> None:
    assert is_cursor_python_gate_misfire("cursor README.md") is False


def test_allows_python_running_the_gate() -> None:
    assert (
        is_cursor_python_gate_misfire(
            "python code_rules_gate.py --base origin/main"
        )
        is False
    )


def test_allows_invoke_item() -> None:
    assert (
        is_cursor_python_gate_misfire("Invoke-Item -LiteralPath 'C:\\tmp\\a.py'")
        is False
    )


def test_allows_empty_command() -> None:
    assert is_cursor_python_gate_misfire("") is False


def test_corrective_message_names_python_and_invoke_item() -> None:
    assert "python" in CORRECTIVE_MESSAGE
    assert "Invoke-Item -LiteralPath" in CORRECTIVE_MESSAGE
    assert "EPIPE" in CORRECTIVE_MESSAGE


def _run_main_with_io(input_text: str) -> str:
    with mock.patch("sys.stdin", io.StringIO(input_text)):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            try:
                hook_module.main()
            except SystemExit:
                pass
            return mock_stdout.getvalue()


def test_main_denies_bash_misfire() -> None:
    hook_input = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "cursor code_rules_gate.py --base origin/main",
        },
    }
    output_text = _run_main_with_io(json.dumps(hook_input))
    output = json.loads(output_text)
    assert output["hookSpecificOutput"]["permissionDecision"] == DENY_DECISION
    assert "cursor-python-misfire" in output["hookSpecificOutput"][
        "permissionDecisionReason"
    ]


def test_main_denies_powershell_misfire() -> None:
    hook_input = {
        "tool_name": "PowerShell",
        "tool_input": {
            "command": "cursor.cmd code_rules_gate.py --staged",
        },
    }
    output_text = _run_main_with_io(json.dumps(hook_input))
    output = json.loads(output_text)
    assert output["hookSpecificOutput"]["permissionDecision"] == DENY_DECISION


def test_main_passes_python_gate_run() -> None:
    hook_input = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "python code_rules_gate.py --base origin/main",
        },
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_wrong_tool_name() -> None:
    hook_input = {
        "tool_name": "Write",
        "tool_input": {
            "command": "cursor code_rules_gate.py --base origin/main",
        },
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_malformed_json() -> None:
    assert _run_main_with_io("not valid json {{{") == ""


def test_main_passes_when_tool_input_is_null() -> None:
    hook_input = {
        "tool_name": "Bash",
        "tool_input": None,
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""
