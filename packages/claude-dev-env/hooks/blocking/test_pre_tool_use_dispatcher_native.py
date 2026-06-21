"""Native-equivalence tests for the nativized PreToolUse hosted hooks.

For each hook the dispatcher runs natively (state_description_blocker and
plain_language_blocker), this suite asserts the native evaluate() call and the
hook's standalone __main__ subprocess path decide identically on the same
payload: same allow-or-deny, same deny-reason text. It also asserts the
dispatcher reaches the same decision through its native path.

The corpus pairs allowing payloads with denying payloads for each hook so the
equivalence holds across both outcomes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from hooks_constants.pre_tool_use_dispatcher_constants import (  # noqa: E402, I001
    DENY_DECISION,
    EDIT_TOOL_NAME,
    MULTI_EDIT_TOOL_NAME,
    WRITE_TOOL_NAME,
)
import plain_language_blocker  # noqa: E402, I001
import state_description_blocker  # noqa: E402, I001

_BLOCKING_DIR = Path(__file__).resolve().parent
_STATE_DESCRIPTION_SCRIPT = str(_BLOCKING_DIR / "state_description_blocker.py")
_PLAIN_LANGUAGE_SCRIPT = str(_BLOCKING_DIR / "plain_language_blocker.py")
_DISPATCHER_SCRIPT = str(_BLOCKING_DIR / "pre_tool_use_dispatcher.py")

_MARKDOWN_PATH = "docs/native_equivalence_probe.md"
_PYTHON_PATH = "src/native_equivalence_probe.py"

_STATE_DESCRIPTION_ALLOW_CONTENT = "# Guide\n\nThe API uses port 8080.\n"
_STATE_DESCRIPTION_DENY_CONTENT = "# Guide\n\nPreviously the system used port 8080.\n"
_PLAIN_LANGUAGE_ALLOW_CONTENT = "# Guide\n\nStart the build to make the report.\n"
_PLAIN_LANGUAGE_DENY_CONTENT = "# Guide\n\nUtilize this to commence the process.\n"


def _write_payload_dictionary(file_path: str, content: str) -> dict[str, object]:
    """Build a Write tool payload dict.

    Args:
        file_path: The target file path.
        content: The file content to write.

    Returns:
        The PreToolUse payload dict for a Write tool call.
    """
    return {
        "tool_name": WRITE_TOOL_NAME,
        "tool_input": {"file_path": file_path, "content": content},
    }


def _edit_payload_dictionary(file_path: str, new_string: str) -> dict[str, object]:
    """Build an Edit tool payload dict.

    Args:
        file_path: The target file path.
        new_string: The replacement text.

    Returns:
        The PreToolUse payload dict for an Edit tool call.
    """
    return {
        "tool_name": EDIT_TOOL_NAME,
        "tool_input": {
            "file_path": file_path,
            "old_string": "old line",
            "new_string": new_string,
        },
    }


def _multi_edit_payload_dictionary(file_path: str, new_string: str) -> dict[str, object]:
    """Build a MultiEdit tool payload dict.

    Args:
        file_path: The target file path.
        new_string: The replacement text for the single edit.

    Returns:
        The PreToolUse payload dict for a MultiEdit tool call.
    """
    return {
        "tool_name": MULTI_EDIT_TOOL_NAME,
        "tool_input": {
            "file_path": file_path,
            "edits": [{"old_string": "old line", "new_string": new_string}],
        },
    }


def _run_script_subprocess(script_path: str, payload_dictionary: dict[str, object]) -> str:
    """Run a hook script as a subprocess and return its stripped stdout.

    Args:
        script_path: Absolute path of the hook script to run.
        payload_dictionary: The payload dict to send as JSON on stdin.

    Returns:
        The hook's stdout text, stripped of surrounding whitespace.
    """
    completed_process = subprocess.run(
        [sys.executable, script_path],
        check=False,
        input=json.dumps(payload_dictionary),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed_process.stdout.strip()


def _deny_reason_from_script_stdout(stdout_text: str) -> str | None:
    """Parse a script's stdout into its deny-reason text, or None for allow.

    Args:
        stdout_text: The script's stripped stdout.

    Returns:
        The permissionDecisionReason text when the script denied, or None when
        the script produced no deny output.
    """
    if not stdout_text:
        return None
    parsed_output = json.loads(stdout_text)
    hook_specific = parsed_output.get("hookSpecificOutput", {})
    if hook_specific.get("permissionDecision") != DENY_DECISION:
        return None
    reason_text = hook_specific.get("permissionDecisionReason", "")
    return reason_text if isinstance(reason_text, str) else None


def _deny_reason_from_dispatcher(payload_dictionary: dict[str, object]) -> str | None:
    """Run the dispatcher as a subprocess and return its deny-reason text.

    Args:
        payload_dictionary: The payload dict to send as JSON on stdin.

    Returns:
        The dispatcher's combined permissionDecisionReason when it denies, or
        None when it allows.
    """
    completed_process = subprocess.run(
        [sys.executable, _DISPATCHER_SCRIPT],
        check=False,
        input=json.dumps(payload_dictionary),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return _deny_reason_from_script_stdout(completed_process.stdout.strip())


def _deny_payload_from_dispatcher(payload_dictionary: dict[str, object]) -> dict[str, object]:
    """Run the dispatcher as a subprocess and return its parsed deny payload.

    Args:
        payload_dictionary: The payload dict to send as JSON on stdin.

    Returns:
        The dispatcher's emitted deny JSON parsed into a dict.
    """
    completed_process = subprocess.run(
        [sys.executable, _DISPATCHER_SCRIPT],
        check=False,
        input=json.dumps(payload_dictionary),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    parsed_payload = json.loads(completed_process.stdout.strip())
    assert isinstance(parsed_payload, dict)
    return parsed_payload


def test_state_description_native_allows_match_script() -> None:
    """state_description_blocker native allow matches the script's allow."""
    payload_dictionary = _write_payload_dictionary(_MARKDOWN_PATH, _STATE_DESCRIPTION_ALLOW_CONTENT)
    native_reason = state_description_blocker.evaluate(payload_dictionary)
    script_stdout = _run_script_subprocess(_STATE_DESCRIPTION_SCRIPT, payload_dictionary)
    script_reason = _deny_reason_from_script_stdout(script_stdout)
    assert native_reason is None
    assert script_reason is None


def test_state_description_native_deny_matches_script_reason() -> None:
    """state_description_blocker native deny reason matches the script's reason."""
    payload_dictionary = _write_payload_dictionary(_MARKDOWN_PATH, _STATE_DESCRIPTION_DENY_CONTENT)
    native_reason = state_description_blocker.evaluate(payload_dictionary)
    script_stdout = _run_script_subprocess(_STATE_DESCRIPTION_SCRIPT, payload_dictionary)
    script_reason = _deny_reason_from_script_stdout(script_stdout)
    assert native_reason is not None
    assert native_reason == script_reason


def test_state_description_native_edit_deny_matches_script_reason() -> None:
    """state_description_blocker native and script agree on an Edit denial."""
    payload_dictionary = _edit_payload_dictionary(
        _MARKDOWN_PATH, "Previously this used the old client.\n"
    )
    native_reason = state_description_blocker.evaluate(payload_dictionary)
    script_stdout = _run_script_subprocess(_STATE_DESCRIPTION_SCRIPT, payload_dictionary)
    script_reason = _deny_reason_from_script_stdout(script_stdout)
    assert native_reason is not None
    assert native_reason == script_reason


def test_state_description_native_non_target_tool_allows_match_script() -> None:
    """state_description_blocker native allows MultiEdit, matching the script."""
    payload_dictionary = _multi_edit_payload_dictionary(
        _MARKDOWN_PATH, _STATE_DESCRIPTION_DENY_CONTENT
    )
    native_reason = state_description_blocker.evaluate(payload_dictionary)
    script_stdout = _run_script_subprocess(_STATE_DESCRIPTION_SCRIPT, payload_dictionary)
    script_reason = _deny_reason_from_script_stdout(script_stdout)
    assert native_reason is None
    assert script_reason is None


def test_plain_language_native_allows_match_script() -> None:
    """plain_language_blocker native allow matches the script's allow."""
    payload_dictionary = _write_payload_dictionary(_MARKDOWN_PATH, _PLAIN_LANGUAGE_ALLOW_CONTENT)
    native_reason = plain_language_blocker.evaluate(payload_dictionary)
    script_stdout = _run_script_subprocess(_PLAIN_LANGUAGE_SCRIPT, payload_dictionary)
    script_reason = _deny_reason_from_script_stdout(script_stdout)
    assert native_reason is None
    assert script_reason is None


def test_plain_language_native_deny_matches_script_reason() -> None:
    """plain_language_blocker native deny reason matches the script's reason."""
    payload_dictionary = _write_payload_dictionary(_MARKDOWN_PATH, _PLAIN_LANGUAGE_DENY_CONTENT)
    native_reason = plain_language_blocker.evaluate(payload_dictionary)
    script_stdout = _run_script_subprocess(_PLAIN_LANGUAGE_SCRIPT, payload_dictionary)
    script_reason = _deny_reason_from_script_stdout(script_stdout)
    assert native_reason is not None
    assert native_reason == script_reason


def test_plain_language_native_multi_edit_deny_matches_script_reason() -> None:
    """plain_language_blocker native and script agree on a MultiEdit denial."""
    payload_dictionary = _multi_edit_payload_dictionary(
        _MARKDOWN_PATH, "Utilize this to commence the process.\n"
    )
    native_reason = plain_language_blocker.evaluate(payload_dictionary)
    script_stdout = _run_script_subprocess(_PLAIN_LANGUAGE_SCRIPT, payload_dictionary)
    script_reason = _deny_reason_from_script_stdout(script_stdout)
    assert native_reason is not None
    assert native_reason == script_reason


def test_plain_language_native_non_markdown_allows_match_script() -> None:
    """plain_language_blocker native allows a non-markdown Write, matching the script."""
    payload_dictionary = _write_payload_dictionary(_PYTHON_PATH, _PLAIN_LANGUAGE_DENY_CONTENT)
    native_reason = plain_language_blocker.evaluate(payload_dictionary)
    script_stdout = _run_script_subprocess(_PLAIN_LANGUAGE_SCRIPT, payload_dictionary)
    script_reason = _deny_reason_from_script_stdout(script_stdout)
    assert native_reason is None
    assert script_reason is None


def test_dispatcher_native_path_denies_state_description() -> None:
    """The dispatcher's native path denies a state_description_blocker violation."""
    payload_dictionary = _write_payload_dictionary(_MARKDOWN_PATH, _STATE_DESCRIPTION_DENY_CONTENT)
    native_reason = state_description_blocker.evaluate(payload_dictionary)
    dispatcher_reason = _deny_reason_from_dispatcher(payload_dictionary)
    assert native_reason is not None
    assert dispatcher_reason is not None
    assert native_reason in dispatcher_reason


def test_dispatcher_native_path_denies_plain_language() -> None:
    """The dispatcher's native path denies a plain_language_blocker violation."""
    payload_dictionary = _multi_edit_payload_dictionary(
        _MARKDOWN_PATH, "Utilize this to commence the process.\n"
    )
    native_reason = plain_language_blocker.evaluate(payload_dictionary)
    dispatcher_reason = _deny_reason_from_dispatcher(payload_dictionary)
    assert native_reason is not None
    assert dispatcher_reason is not None
    assert native_reason in dispatcher_reason


def test_dispatcher_native_plain_language_carries_system_message() -> None:
    """The dispatcher's plain-language deny carries the standalone systemMessage."""
    payload_dictionary = _write_payload_dictionary(_MARKDOWN_PATH, _PLAIN_LANGUAGE_DENY_CONTENT)
    deny_reason = plain_language_blocker.evaluate(payload_dictionary)
    assert deny_reason is not None
    standalone_payload = plain_language_blocker.build_deny_payload(deny_reason)
    expected_system_message = standalone_payload["systemMessage"]
    assert isinstance(expected_system_message, str)
    dispatcher_payload = _deny_payload_from_dispatcher(payload_dictionary)
    dispatcher_system_message = dispatcher_payload.get("systemMessage")
    assert isinstance(dispatcher_system_message, str)
    assert expected_system_message in dispatcher_system_message


def test_dispatcher_native_plain_language_carries_suppress_output() -> None:
    """The dispatcher's plain-language deny carries the standalone suppressOutput flag."""
    payload_dictionary = _write_payload_dictionary(_MARKDOWN_PATH, _PLAIN_LANGUAGE_DENY_CONTENT)
    dispatcher_payload = _deny_payload_from_dispatcher(payload_dictionary)
    assert dispatcher_payload.get("suppressOutput") is True


def test_dispatcher_native_state_description_carries_additional_context() -> None:
    """The dispatcher's state-description deny carries the standalone additionalContext."""
    payload_dictionary = _write_payload_dictionary(_MARKDOWN_PATH, _STATE_DESCRIPTION_DENY_CONTENT)
    deny_reason = state_description_blocker.evaluate(payload_dictionary)
    assert deny_reason is not None
    standalone_payload = state_description_blocker.build_deny_payload(deny_reason)
    standalone_hook_specific = standalone_payload["hookSpecificOutput"]
    assert isinstance(standalone_hook_specific, dict)
    expected_additional_context = standalone_hook_specific["additionalContext"]
    dispatcher_payload = _deny_payload_from_dispatcher(payload_dictionary)
    dispatcher_hook_specific = dispatcher_payload.get("hookSpecificOutput", {})
    assert isinstance(dispatcher_hook_specific, dict)
    assert dispatcher_hook_specific.get("additionalContext") == expected_additional_context


def test_dispatcher_native_state_description_carries_system_message() -> None:
    """The dispatcher's state-description deny carries the standalone systemMessage."""
    payload_dictionary = _write_payload_dictionary(_MARKDOWN_PATH, _STATE_DESCRIPTION_DENY_CONTENT)
    deny_reason = state_description_blocker.evaluate(payload_dictionary)
    assert deny_reason is not None
    standalone_payload = state_description_blocker.build_deny_payload(deny_reason)
    expected_system_message = standalone_payload["systemMessage"]
    assert isinstance(expected_system_message, str)
    dispatcher_payload = _deny_payload_from_dispatcher(payload_dictionary)
    dispatcher_system_message = dispatcher_payload.get("systemMessage")
    assert isinstance(dispatcher_system_message, str)
    assert expected_system_message in dispatcher_system_message
