"""Behavior tests for code_rules_enforcer's MultiEdit reconstruction.

A MultiEdit payload carries an ``edits`` list rather than a single
``old_string``/``new_string`` pair. These tests prove the enforcer reconstructs
the whole post-edit file from every entry in that list — not only the first —
so a violation introduced by the second or later edit is denied exactly like
one introduced by the first.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code_rules_enforcer import main
from code_rules_enforcer_test_support import run_serialized_payload_entrypoint

_TWO_FUNCTION_SOURCE = (
    "def first_helper() -> int:\n    return 1\n\n\ndef second_helper() -> int:\n    return 2\n"
)


def _production_directory(tmp_path: Path) -> Path:
    """Return a sibling directory whose path carries no test-name substring.

    ``code_rules_enforcer``'s own path-based exemptions treat any path segment
    matching a test-name pattern as a test file, and pytest's ``tmp_path``
    embeds the test function's name, so scanning directly under ``tmp_path``
    would be silently exempted. A sibling directory named after ordinary
    production code sidesteps that.
    """
    production_directory = tmp_path.parent / "multi-edit-prod"
    production_directory.mkdir(exist_ok=True)
    return production_directory


def _multi_edit_payload(file_path: str, all_edits: list[dict[str, str]]) -> str:
    return json.dumps(
        {
            "tool_name": "MultiEdit",
            "tool_input": {"file_path": file_path, "edits": all_edits},
        }
    )


def _run_multi_edit(file_path: str, all_edits: list[dict[str, str]]) -> str:
    stdout_text, _exit_code = run_serialized_payload_entrypoint(
        main, _multi_edit_payload(file_path, all_edits)
    )
    return stdout_text


def test_violation_in_second_edit_is_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A library print() introduced only by the second edit is caught and denied."""
    monkeypatch.setenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", "1")
    target_file = _production_directory(tmp_path) / "services.py"
    target_file.write_text(_TWO_FUNCTION_SOURCE, encoding="utf-8")

    stdout_text = _run_multi_edit(
        str(target_file),
        [
            {"old_string": "return 1", "new_string": "return 11"},
            {
                "old_string": "    return 2",
                "new_string": "    print(2)\n    return 2",
            },
        ],
    )

    assert stdout_text.strip(), "expected a deny payload, got no output"
    deny_payload = json.loads(stdout_text)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    deny_reason = deny_payload["hookSpecificOutput"]["permissionDecisionReason"].lower()
    assert "print" in deny_reason


def test_clean_multi_edit_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MultiEdit whose reconstructed file carries no violation is allowed."""
    monkeypatch.setenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", "1")
    target_file = _production_directory(tmp_path) / "services.py"
    target_file.write_text(_TWO_FUNCTION_SOURCE, encoding="utf-8")

    stdout_text = _run_multi_edit(
        str(target_file),
        [
            {"old_string": "return 1", "new_string": "return 11"},
            {"old_string": "return 2", "new_string": "return 22"},
        ],
    )

    assert stdout_text.strip() == ""
