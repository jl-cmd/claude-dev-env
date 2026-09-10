"""Behavior tests for the MSYS path-conversion advisory hook.

The hook is a PostToolUse observer on Bash. It never blocks. These tests pin
which failed git call wakes it, which lookalike failures stay quiet, and what
the advisory text says.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

try:
    advisory_directory = str(Path(__file__).resolve().parent)
    if advisory_directory not in sys.path:
        sys.path.insert(0, advisory_directory)
    import msys_path_conversion_advisor
    from hooks_constants import msys_path_conversion_advisor_constants
except ImportError as import_error:
    raise ImportError(
        "test_msys_path_conversion_advisor: cannot import its sibling modules; "
        "ensure the advisory directory is importable."
    ) from import_error


_MANGLED_ARGUMENT = r"origin\main;.claude\skills\x\test_run_evals.py"
_MANGLED_FAILURE_RESPONSE = (
    "Error: Exit code 128\n"
    r"fatal: ambiguous argument 'origin\main;.claude\skills\x\test_run_evals.py': "
    "unknown revision or path not in the working tree."
)
_MISSING_REVISION_RESPONSE = (
    "Error: Exit code 128\n"
    "fatal: ambiguous argument 'origin/nope:packages/app/main.py': "
    "unknown revision or path not in the working tree."
)
_MANGLED_OBJECT_NAME_RESPONSE = (
    "Error: Exit code 128\n" + r"fatal: invalid object name 'origin\main;C'."
)
_MISSING_OBJECT_NAME_RESPONSE = (
    "Error: Exit code 128\nfatal: invalid object name 'nosuchbranch'."
)
_SHOW_COMMAND = "git show origin/main:.claude/skills/x/test_run_evals.py"
_ABSOLUTE_PATH_SHOW_COMMAND = "git show origin/main:/nope"
_MISSING_OBJECT_SHOW_COMMAND = "git show nosuchbranch:AGENTS.md"
_EXPORT_LINE = "export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'"


def _payload(command: str, tool_response: object) -> str:
    return json.dumps(
        {
            "session_id": "msys-session",
            "cwd": "C:/repo",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": tool_response,
        }
    )


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payload_text: str,
) -> str:
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload_text))
    msys_path_conversion_advisor.main()
    return capsys.readouterr().out


def test_should_return_the_mangled_argument_word_for_word() -> None:
    mangled_argument = msys_path_conversion_advisor.mangled_revision_path_argument(
        _SHOW_COMMAND, _MANGLED_FAILURE_RESPONSE
    )

    assert mangled_argument == r"origin\main;.claude\skills\x\test_run_evals.py"


def test_should_return_the_mangled_argument_from_an_invalid_object_name_failure() -> None:
    mangled_argument = msys_path_conversion_advisor.mangled_revision_path_argument(
        _ABSOLUTE_PATH_SHOW_COMMAND, _MANGLED_OBJECT_NAME_RESPONSE
    )

    assert mangled_argument == r"origin\main;C"


def test_should_stay_quiet_when_the_object_name_failure_names_an_unmangled_argument() -> None:
    assert (
        msys_path_conversion_advisor.mangled_revision_path_argument(
            _MISSING_OBJECT_SHOW_COMMAND, _MISSING_OBJECT_NAME_RESPONSE
        )
        is None
    )


def test_markers_should_hold_both_git_messages_with_the_ambiguous_argument_first() -> None:
    assert msys_path_conversion_advisor_constants.ALL_MANGLED_ARGUMENT_MARKERS == (
        "fatal: ambiguous argument '",
        "fatal: invalid object name '",
    )


def test_should_stay_quiet_when_the_command_succeeded() -> None:
    zero_exit_response = {"stdout": "", "stderr": ""}

    assert (
        msys_path_conversion_advisor.mangled_revision_path_argument(
            _SHOW_COMMAND, zero_exit_response
        )
        is None
    )


def test_should_stay_quiet_when_the_quoted_argument_is_unmangled() -> None:
    assert (
        msys_path_conversion_advisor.mangled_revision_path_argument(
            "git show origin/nope:packages/app/main.py", _MISSING_REVISION_RESPONSE
        )
        is None
    )


def test_should_stay_quiet_when_the_command_already_exports_the_workaround() -> None:
    already_fixed_command = (
        "export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' && "
        "git show origin/main:.claude/skills/x/test_run_evals.py"
    )

    assert (
        msys_path_conversion_advisor.mangled_revision_path_argument(
            already_fixed_command, _MANGLED_FAILURE_RESPONSE
        )
        is None
    )


def test_should_stay_quiet_without_the_ambiguous_argument_marker() -> None:
    other_failure = "Error: Exit code 1\nfatal: not a git repository"

    assert (
        msys_path_conversion_advisor.mangled_revision_path_argument(_SHOW_COMMAND, other_failure)
        is None
    )


def test_should_stay_quiet_when_the_quoted_argument_never_closes() -> None:
    unterminated_failure = (
        "Error: Exit code 128\n" + r"fatal: ambiguous argument 'origin\main;.claude"
    )

    assert (
        msys_path_conversion_advisor.mangled_revision_path_argument(
            _SHOW_COMMAND, unterminated_failure
        )
        is None
    )


def test_advisory_should_name_the_argument_and_the_export_line() -> None:
    advisory_text = msys_path_conversion_advisor.build_advisory_context(_MANGLED_ARGUMENT)

    assert advisory_text.startswith("=== MSYS PATH CONVERSION")
    assert "never a block" in advisory_text
    assert r"origin\main;.claude\skills\x\test_run_evals.py" in advisory_text
    assert _EXPORT_LINE in advisory_text
    assert "Git Bash rewrote a <rev>:<path> argument" in advisory_text
    assert "same command" in advisory_text


def test_main_should_emit_additional_context_after_a_mangled_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stdout_text = _run_main(monkeypatch, capsys, _payload(_SHOW_COMMAND, _MANGLED_FAILURE_RESPONSE))

    payload = json.loads(stdout_text)
    assert payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    additional_context = str(payload["hookSpecificOutput"]["additionalContext"])
    assert _EXPORT_LINE in additional_context
    assert r"origin\main;.claude\skills\x\test_run_evals.py" in additional_context


def test_main_should_stay_quiet_for_a_non_bash_tool(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = json.loads(_payload(_SHOW_COMMAND, _MANGLED_FAILURE_RESPONSE))
    payload["tool_name"] = "PowerShell"

    assert _run_main(monkeypatch, capsys, json.dumps(payload)) == ""


def test_should_report_a_backslash_argument_as_carrying_a_mangling_mark() -> None:
    assert (
        msys_path_conversion_advisor.argument_carries_msys_mangling_marks(_MANGLED_ARGUMENT)
        is True
    )
