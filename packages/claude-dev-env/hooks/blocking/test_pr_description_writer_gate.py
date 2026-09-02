"""Unit tests for the pr-description-writer PreToolUse gate on gh pr create."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
_HOOKS_DIRECTORY = _BLOCKING_DIRECTORY.parent
for each_directory in (_BLOCKING_DIRECTORY, _HOOKS_DIRECTORY):
    if str(each_directory) not in sys.path:
        sys.path.insert(0, str(each_directory))

_GATE_SPEC = importlib.util.spec_from_file_location(
    "pr_description_writer_gate",
    _BLOCKING_DIRECTORY / "pr_description_writer_gate.py",
)
assert _GATE_SPEC is not None
assert _GATE_SPEC.loader is not None
gate_module = importlib.util.module_from_spec(_GATE_SPEC)
_GATE_SPEC.loader.exec_module(gate_module)

_GATE_CONSTANTS = importlib.import_module(
    "hooks_constants.pr_description_writer_gate_constants"
)
_PR_DESCRIPTION_WRITER_SUBAGENT_TYPE = _GATE_CONSTANTS.PR_DESCRIPTION_WRITER_SUBAGENT_TYPE

_SESSION_ID = "session-abc123"
_PLAIN_CREATE_COMMAND = 'gh pr create --draft --title "feat: add it" --body-file body.md'


def _payload(command: str, tool_name: str = "Bash") -> dict[str, object]:
    """Build a PreToolUse payload carrying one shell command.

    Args:
        command: The shell command the gate inspects.
        tool_name: The tool the command runs through.

    Returns:
        The payload dictionary the gate reads from stdin.
    """
    return {
        "tool_name": tool_name,
        "session_id": _SESSION_ID,
        "tool_input": {"command": command},
    }


def _printed_output_for(command: str, temp_directory: Path, tool_name: str = "Bash") -> str:
    """Run the gate against one command and return everything it printed.

    Args:
        command: The shell command the gate inspects.
        temp_directory: The directory standing in for the system temp root.
        tool_name: The tool the command runs through.

    Returns:
        The gate's stripped stdout — empty on an allow.
    """
    captured_stdout = io.StringIO()
    payload_text = json.dumps(_payload(command, tool_name))
    with (
        mock.patch("sys.stdin", io.StringIO(payload_text)),
        mock.patch("sys.stdout", captured_stdout),
        mock.patch.object(_GATE_CONSTANTS.tempfile, "gettempdir", return_value=str(temp_directory)),
        pytest.raises(SystemExit),
    ):
        gate_module.main()
    return captured_stdout.getvalue().strip()


def _decision_for(command: str, temp_directory: Path, tool_name: str = "Bash") -> str:
    """Return the gate's permission decision for one command.

    Args:
        command: The shell command the gate inspects.
        temp_directory: The directory standing in for the system temp root.
        tool_name: The tool the command runs through.

    Returns:
        The ``permissionDecision`` string, or an empty string on an allow.
    """
    printed_text = _printed_output_for(command, temp_directory, tool_name)
    if not printed_text:
        return ""
    hook_output = json.loads(printed_text).get("hookSpecificOutput", {})
    return str(hook_output.get("permissionDecision", ""))


def _record_spawn(temp_directory: Path, session_id: str = _SESSION_ID) -> None:
    """Write the marker file that stands for a recorded agent spawn.

    Args:
        temp_directory: The directory standing in for the system temp root.
    """
    marker_name = (
        f"{_GATE_CONSTANTS.SPAWN_MARKER_FILE_PREFIX}{session_id}"
        f"{_GATE_CONSTANTS.SPAWN_MARKER_FILE_SUFFIX}"
    )
    (temp_directory / marker_name).touch()


def should_deny_pr_create_with_no_recorded_spawn(tmp_path: Path) -> None:
    """A gh pr create with no recorded spawn is denied."""
    assert _decision_for(_PLAIN_CREATE_COMMAND, tmp_path) == "deny"


def should_allow_pr_create_after_a_recorded_spawn(tmp_path: Path) -> None:
    """A gh pr create is allowed once this session recorded a spawn."""
    _record_spawn(tmp_path)
    assert _decision_for(_PLAIN_CREATE_COMMAND, tmp_path) == ""


def should_allow_pr_create_carrying_the_bypass_marker(tmp_path: Path) -> None:
    """A trailing bypass comment allows the create with no recorded spawn."""
    command = f"{_PLAIN_CREATE_COMMAND} {gate_module.SPAWN_BYPASS_MARKER}"
    assert _decision_for(command, tmp_path) == ""


def should_allow_multiline_pr_create_carrying_the_bypass_marker(tmp_path: Path) -> None:
    """A final bypass comment allows a create after a continued shell line."""
    command = f"cd . && \\\n+{_PLAIN_CREATE_COMMAND} {gate_module.SPAWN_BYPASS_MARKER}"
    assert _decision_for(command, tmp_path) == ""


def should_deny_when_the_bypass_marker_follows_another_shell_segment(tmp_path: Path) -> None:
    """A final marker for echo cannot opt a preceding create out."""
    command = f"{_PLAIN_CREATE_COMMAND} && echo {gate_module.SPAWN_BYPASS_MARKER}"
    assert _decision_for(command, tmp_path) == "deny"


def should_deny_when_only_another_session_has_a_spawn_marker(tmp_path: Path) -> None:
    """A marker from another session cannot unlock this session's create."""
    _record_spawn(tmp_path, session_id="earlier-session")
    assert _decision_for(_PLAIN_CREATE_COMMAND, tmp_path) == "deny"


def should_deny_when_the_marker_text_sits_inside_a_quoted_value(tmp_path: Path) -> None:
    """The bypass text inside a quoted title leaves the gate running."""
    command = 'gh pr create --title "fix # pr-description-skip" --body-file body.md'
    assert _decision_for(command, tmp_path) == "deny"


def should_deny_a_pr_create_that_follows_another_command(tmp_path: Path) -> None:
    """A create in a later command segment is still gated."""
    command = f"cd /repo && {_PLAIN_CREATE_COMMAND}"
    assert _decision_for(command, tmp_path) == "deny"


@pytest.mark.parametrize("shell_tool_name", ["Bash", "PowerShell"])
def should_gate_each_shell_tool(shell_tool_name: str, tmp_path: Path) -> None:
    """Both shell tools reach the gate."""
    decision = _decision_for(_PLAIN_CREATE_COMMAND, tmp_path, tool_name=shell_tool_name)
    assert decision == "deny"


@pytest.mark.parametrize(
    "unrelated_command",
    [
        "gh pr edit 12 --body-file body.md",
        "gh pr comment 12 --body-file body.md",
        "gh pr ready 12",
        "gh issue create --title x --body-file body.md",
        "git commit -m x",
        "echo gh pr create",
    ],
)
def should_stay_quiet_for_a_command_that_creates_no_pull_request(
    unrelated_command: str, tmp_path: Path
) -> None:
    """A command other than gh pr create passes untouched."""
    assert _decision_for(unrelated_command, tmp_path) == ""


def should_stay_quiet_for_a_tool_that_runs_no_shell(tmp_path: Path) -> None:
    """A non-shell tool carrying the same text passes untouched."""
    assert _decision_for(_PLAIN_CREATE_COMMAND, tmp_path, tool_name="Write") == ""


def should_deny_when_the_payload_names_no_session(tmp_path: Path) -> None:
    """A payload with no session id reads as no record and denies.

    A shared fallback marker would let one session's spawn silently clear a
    later session's create, so an unusable session id denies instead.
    """
    _record_spawn(tmp_path)
    captured_stdout = io.StringIO()
    payload = _payload(_PLAIN_CREATE_COMMAND)
    payload["session_id"] = ""
    with (
        mock.patch("sys.stdin", io.StringIO(json.dumps(payload))),
        mock.patch("sys.stdout", captured_stdout),
        mock.patch.object(_GATE_CONSTANTS.tempfile, "gettempdir", return_value=str(tmp_path)),
        pytest.raises(SystemExit),
    ):
        gate_module.main()
    hook_output = json.loads(captured_stdout.getvalue().strip())["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "deny"


def should_allow_an_untokenizable_command(tmp_path: Path) -> None:
    """A command that will not tokenize fails open."""
    assert _decision_for('gh pr create --title "unclosed', tmp_path) == ""


def should_name_both_ways_forward_in_the_denial(tmp_path: Path) -> None:
    """The denial text names the agent spawn and the bypass marker."""
    printed_text = _printed_output_for(_PLAIN_CREATE_COMMAND, tmp_path)
    denial_reason = json.loads(printed_text)["hookSpecificOutput"]["permissionDecisionReason"]
    assert _PR_DESCRIPTION_WRITER_SUBAGENT_TYPE in denial_reason
    assert gate_module.SPAWN_BYPASS_MARKER in denial_reason


def should_read_the_marker_path_the_shared_builder_produces(tmp_path: Path) -> None:
    """The gate reads exactly the file the shared path builder names.

    The tracker writes through `spawn_marker_path` and the gate reads through it,
    so neither side owns a private copy of the marker file name.
    """
    marker_file = _GATE_CONSTANTS.spawn_marker_path(_SESSION_ID, temp_directory=tmp_path)
    assert marker_file is not None
    marker_file.touch()
    assert _decision_for(_PLAIN_CREATE_COMMAND, tmp_path) == ""


def should_deny_when_the_session_id_names_no_marker(tmp_path: Path) -> None:
    """A session id that sanitizes to nothing yields no path, so the gate denies."""
    assert _GATE_CONSTANTS.spawn_marker_path("", temp_directory=tmp_path) is None
