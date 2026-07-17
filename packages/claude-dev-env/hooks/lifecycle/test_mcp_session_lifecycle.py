"""Behavior tests for MCP session host registry and descendant teardown."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from pathlib import Path

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_TREE = _HOOK_DIR.parent
for each_path in (str(_HOOK_DIR), str(_HOOKS_TREE)):
    if each_path not in sys.path:
        sys.path.insert(0, each_path)

hook_spec = importlib.util.spec_from_file_location(
    "mcp_session_lifecycle",
    _HOOK_DIR / "mcp_session_lifecycle.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
lifecycle = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(lifecycle)


def test_command_line_matches_mcp_server_detects_mcpvault() -> None:
    command_line = (
        r"cmd.exe /c npx @bitbonsai/mcpvault@latest C:/Users/example/SessionLog"
    )
    assert lifecycle.command_line_matches_mcp_server(command_line) is True


def test_command_line_matches_mcp_server_detects_serena() -> None:
    command_line = (
        r"uvx --from git+https://github.com/oraios/serena "
        r"serena start-mcp-server"
    )
    assert lifecycle.command_line_matches_mcp_server(command_line) is True


def test_command_line_matches_mcp_server_rejects_unrelated() -> None:
    assert lifecycle.command_line_matches_mcp_server("node server.js") is False
    assert lifecycle.command_line_matches_mcp_server("") is False


def test_write_and_read_host_pid_registry_round_trip(tmp_path: Path) -> None:
    registry_directory = str(tmp_path / "registry")
    lifecycle.write_host_pid_registry(
        session_id="session-abc",
        host_pid=4242,
        registry_directory=registry_directory,
    )
    host_pid = lifecycle.read_host_pid_registry(
        session_id="session-abc",
        registry_directory=registry_directory,
    )
    assert host_pid == 4242


def test_sanitize_session_id_strips_path_traversal() -> None:
    assert ".." not in lifecycle.sanitize_session_id("../evil")
    assert lifecycle.sanitize_session_id("") == "unknown-session"


def test_collect_mcp_descendant_process_ids_scopes_to_host() -> None:
    all_processes: list[dict[str, object]] = [
        {"ProcessId": 100, "ParentProcessId": 1, "CommandLine": "claude.exe"},
        {
            "ProcessId": 200,
            "ParentProcessId": 100,
            "CommandLine": "cmd /c npx @bitbonsai/mcpvault@latest vault",
        },
        {
            "ProcessId": 201,
            "ParentProcessId": 200,
            "CommandLine": "node mcpvault/dist/server.js vault",
        },
        {
            "ProcessId": 300,
            "ParentProcessId": 1,
            "CommandLine": "cmd /c npx @bitbonsai/mcpvault@latest other",
        },
        {
            "ProcessId": 400,
            "ParentProcessId": 100,
            "CommandLine": "node unrelated.js",
        },
    ]
    matched_process_ids = lifecycle.collect_mcp_descendant_process_ids(
        host_pid=100,
        all_processes=all_processes,
    )
    assert 200 in matched_process_ids
    assert 201 in matched_process_ids
    assert 300 not in matched_process_ids
    assert 400 not in matched_process_ids


def test_is_descendant_of_host_handles_multi_level_chain() -> None:
    all_parent_pid_by_child_pid = {50: 10, 60: 50}
    assert (
        lifecycle.is_descendant_of_host(
            process_id=60,
            host_pid=10,
            all_parent_pid_by_child_pid=all_parent_pid_by_child_pid,
        )
        is True
    )
    assert (
        lifecycle.is_descendant_of_host(
            process_id=60,
            host_pid=99,
            all_parent_pid_by_child_pid=all_parent_pid_by_child_pid,
        )
        is False
    )


def test_run_session_lifecycle_registers_on_session_start(tmp_path: Path) -> None:
    registry_directory = str(tmp_path / "registry")
    action_label = lifecycle.run_session_lifecycle(
        payload_by_field={
            "session_id": "sess-1",
            "hook_event_name": "SessionStart",
            "source": "startup",
        },
        host_pid=555,
        registry_directory=registry_directory,
        all_processes=[],
    )
    assert action_label == "registered"
    assert (
        lifecycle.read_host_pid_registry(
            session_id="sess-1",
            registry_directory=registry_directory,
        )
        == 555
    )


def test_run_session_lifecycle_teardown_uses_registry_and_deletes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_directory = str(tmp_path / "registry")
    lifecycle.write_host_pid_registry(
        session_id="sess-2",
        host_pid=100,
        registry_directory=registry_directory,
    )
    all_terminated_process_ids: list[int] = []

    def _fake_terminate(process_id: int) -> bool:
        all_terminated_process_ids.append(process_id)
        return True

    monkeypatch.setattr(lifecycle, "terminate_process_tree", _fake_terminate)
    all_processes: list[dict[str, object]] = [
        {
            "ProcessId": 200,
            "ParentProcessId": 100,
            "CommandLine": "npx @playwright/mcp@latest",
        },
        {
            "ProcessId": 201,
            "ParentProcessId": 999,
            "CommandLine": "npx @playwright/mcp@latest",
        },
    ]
    action_label = lifecycle.run_session_lifecycle(
        payload_by_field={
            "session_id": "sess-2",
            "hook_event_name": "SessionEnd",
        },
        host_pid=1,
        registry_directory=registry_directory,
        all_processes=all_processes,
    )
    assert action_label == "torn_down"
    assert all_terminated_process_ids == [200]
    assert (
        lifecycle.read_host_pid_registry(
            session_id="sess-2",
            registry_directory=registry_directory,
        )
        is None
    )


def test_parse_process_list_json_accepts_single_object() -> None:
    payload = json.dumps(
        {"ProcessId": 1, "ParentProcessId": 0, "CommandLine": "x"}
    )
    all_processes = lifecycle.parse_process_list_json(payload)
    assert len(all_processes) == 1
    assert all_processes[0]["ProcessId"] == 1
