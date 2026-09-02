"""Behavior tests for migration_safety_advisor through its production entry paths."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


_ADVISORY_DIRECTORY = Path(__file__).resolve().parent
_HOOKS_DIRECTORY = _ADVISORY_DIRECTORY.parent
_ADVISOR_SCRIPT = _ADVISORY_DIRECTORY / "migration_safety_advisor.py"
_DISPATCHER_SCRIPT = _HOOKS_DIRECTORY / "blocking" / "pre_tool_use_dispatcher.py"


def _run_hook(script_path: Path, payload: dict[str, object]) -> dict[str, object] | None:
    completed_process = subprocess.run(
        [sys.executable, str(script_path)],
        check=False,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed_process.returncode == 0
    if not completed_process.stdout.strip():
        return None
    parsed_payload = json.loads(completed_process.stdout)
    assert isinstance(parsed_payload, dict)
    return parsed_payload


def _build_edit_payload(file_path: Path, new_string: str) -> dict[str, object]:
    return {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(file_path),
            "old_string": "operations = []",
            "new_string": new_string,
        },
    }


def _build_control_payload(tool_name: str, file_path: Path, content: str) -> dict[str, object]:
    if tool_name == "Write":
        tool_input: dict[str, object] = {
            "file_path": str(file_path),
            "content": content,
        }
    else:
        tool_input = {
            "file_path": str(file_path),
            "edits": [{"old_string": "operations = []", "new_string": content}],
        }
    return {"tool_name": tool_name, "tool_input": tool_input}


def _prepare_fresh_test_pair(migration_path: Path) -> None:
    """Write a migration module and its paired test file."""
    migration_path.parent.mkdir(parents=True)
    migration_path.write_text("operations = []\n", encoding="utf-8")
    test_path = migration_path.with_name(f"test_{migration_path.stem}.py")
    test_path.write_text("def test_migration_contract():\n    assert True\n", encoding="utf-8")


def _permission_fields(parsed_payload: dict[str, object]) -> dict[str, object]:
    hook_specific = parsed_payload.get("hookSpecificOutput", {})
    assert isinstance(hook_specific, dict)
    return hook_specific


def _text_field(field_by_key: dict[str, object], field_name: str) -> str:
    field_value = field_by_key.get(field_name)
    assert isinstance(field_value, str)
    return field_value


def test_standalone_advisor_warns_for_unsafe_migration_edit(tmp_path: Path) -> None:
    migration_path = tmp_path / "billing" / "migrations" / "0002_remove_name.py"
    payload = _build_edit_payload(migration_path, 'operations = [migrations.RemoveField("name")]')

    advisory_payload = _run_hook(_ADVISOR_SCRIPT, payload)
    assert advisory_payload is not None
    permission_fields = _permission_fields(advisory_payload)

    assert permission_fields["permissionDecision"] == "allow"
    assert "RemoveField" in _text_field(permission_fields, "additionalContext")
    assert "MIGRATION SAFETY" in _text_field(advisory_payload, "systemMessage")


def test_dispatcher_surfaces_migration_warning_for_edit(tmp_path: Path) -> None:
    migration_path = tmp_path / "billing" / "migrations" / "0002_remove_name.py"
    _prepare_fresh_test_pair(migration_path)
    payload = _build_edit_payload(migration_path, 'operations = [migrations.RemoveField("name")]')

    dispatched_payload = _run_hook(_DISPATCHER_SCRIPT, payload)
    assert dispatched_payload is not None
    permission_fields = _permission_fields(dispatched_payload)

    assert permission_fields["permissionDecision"] == "allow"
    assert "RemoveField" in _text_field(permission_fields, "additionalContext")
    assert "MIGRATION SAFETY" in _text_field(dispatched_payload, "systemMessage")


def test_dispatcher_keeps_migration_advisor_write_excluded(tmp_path: Path) -> None:
    """Write stays out of the migration advisor's roster; only Edit and MultiEdit reach it."""
    migration_path = tmp_path / "billing" / "migrations" / "0002_remove_name.py"
    _prepare_fresh_test_pair(migration_path)
    payload = _build_control_payload(
        "Write",
        migration_path,
        'operations = [migrations.RemoveField("name")]',
    )

    dispatched_payload = _run_hook(_DISPATCHER_SCRIPT, payload)
    serialized_payload = json.dumps(dispatched_payload or {})

    assert "MIGRATION SAFETY" not in serialized_payload


def test_dispatcher_extends_migration_advisor_to_multi_edit(tmp_path: Path) -> None:
    """A MultiEdit reaches the migration advisor the same way an Edit does."""
    migration_path = tmp_path / "billing" / "migrations" / "0002_remove_name.py"
    _prepare_fresh_test_pair(migration_path)
    payload = _build_control_payload(
        "MultiEdit",
        migration_path,
        'operations = [migrations.RemoveField("name")]',
    )

    dispatched_payload = _run_hook(_DISPATCHER_SCRIPT, payload)
    assert dispatched_payload is not None
    serialized_payload = json.dumps(dispatched_payload)

    assert "MIGRATION SAFETY" in serialized_payload


def _build_multi_edit_payload(
    file_path: Path, all_edits: list[dict[str, str]]
) -> dict[str, object]:
    return {
        "tool_name": "MultiEdit",
        "tool_input": {"file_path": str(file_path), "edits": all_edits},
    }


def test_standalone_advisor_warns_for_unsafe_operation_in_second_multi_edit(
    tmp_path: Path,
) -> None:
    """An unsafe operation in the second edit of a MultiEdit is caught, not only the first.

    migration_safety_advisor has no tool_name gate today: it reads
    tool_input.get("new_string"), a key a MultiEdit payload never carries at
    the top level. Widening its roster entry alone would silently do
    nothing on a real MultiEdit call.
    """
    migration_path = tmp_path / "billing" / "migrations" / "0002_remove_name.py"
    payload = _build_multi_edit_payload(
        migration_path,
        [
            {"old_string": "operations = []", "new_string": "operations = [migrations.AddField()]"},
            {
                "old_string": "migrations.AddField()",
                "new_string": 'migrations.AddField(), migrations.RemoveField("name")',
            },
        ],
    )

    advisory_payload = _run_hook(_ADVISOR_SCRIPT, payload)
    assert advisory_payload is not None
    permission_fields = _permission_fields(advisory_payload)

    assert permission_fields["permissionDecision"] == "allow"
    assert "RemoveField" in _text_field(permission_fields, "additionalContext")


def test_standalone_advisor_is_silent_for_a_clean_multi_edit(tmp_path: Path) -> None:
    migration_path = tmp_path / "billing" / "migrations" / "0002_remove_name.py"
    payload = _build_multi_edit_payload(
        migration_path,
        [{"old_string": "operations = []", "new_string": "operations = [migrations.AddField()]"}],
    )

    advisory_payload = _run_hook(_ADVISOR_SCRIPT, payload)
    assert advisory_payload is None
