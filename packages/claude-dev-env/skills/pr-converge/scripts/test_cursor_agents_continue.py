"""Tests for the Cursor Agents AutoHotkey pacer."""

from __future__ import annotations

from pathlib import Path


def _script_text() -> str:
    return (Path(__file__).resolve().parent / "cursor-agents-continue.ahk").read_text(
        encoding="utf-8"
    )


def _function_body(function_name: str, next_marker: str) -> str:
    script_text = _script_text()
    function_start = script_text.index(function_name)
    function_end = script_text.index(next_marker, function_start)
    return script_text[function_start:function_end]


def test_should_fallback_when_pwsh_is_unavailable() -> None:
    script_text = _script_text()
    terminate_body = _function_body(
        "terminate_other_script_instances() {",
        "\n}\n\nrun_stop_script_with_shell",
    )
    helper_body = _function_body(
        "run_stop_script_with_shell(shell_name, stop_script) {",
        "\n}\n\nterminate_other_script_instances()",
    )

    first_shell_check = (
        "if run_stop_script_with_shell(POWERSHELL_CORE_SHELL_NAME, stop_script)"
    )
    fallback_shell_check = (
        "if run_stop_script_with_shell(WINDOWS_POWERSHELL_SHELL_NAME, stop_script)"
    )

    assert 'POWERSHELL_CORE_SHELL_NAME := "pwsh"' in script_text
    assert 'WINDOWS_POWERSHELL_SHELL_NAME := "powershell.exe"' in script_text
    assert "STOP_SCRIPT_ARGUMENTS_FORMAT :=" in script_text
    assert 'RUN_WAIT_WINDOW_OPTION := "Hide"' in script_text
    assert first_shell_check in terminate_body
    assert fallback_shell_check in terminate_body
    assert "throw Error(Format(STOP_SCRIPT_FAILURE_MESSAGE_FORMAT" in terminate_body
    assert terminate_body.index(first_shell_check) < terminate_body.index(
        fallback_shell_check
    )
    assert terminate_body.index(fallback_shell_check) < terminate_body.index(
        "throw Error"
    )
    assert '"pwsh"' not in terminate_body
    assert '"powershell.exe"' not in terminate_body
    assert "try {" in helper_body
    assert "catch {" in helper_body
    assert (
        "Format(STOP_SCRIPT_ARGUMENTS_FORMAT, stop_script, ProcessExist())"
        in helper_body
    )
    assert (
        "RunWait(shell_name stop_command_arguments, , RUN_WAIT_WINDOW_OPTION)"
        in helper_body
    )
    assert "-NoProfile" not in helper_body
    assert '"Hide"' not in helper_body
