"""Tests for dead-parent MCP orphan reaping."""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

_SCRIPT_DIR = pathlib.Path(__file__).parent
_SCRIPTS_DIR = _SCRIPT_DIR.parent
for each_path in (str(_SCRIPT_DIR), str(_SCRIPTS_DIR)):
    if each_path not in sys.path:
        sys.path.insert(0, each_path)

module_spec = importlib.util.spec_from_file_location(
    "reap_orphaned_mcp_processes",
    _SCRIPT_DIR / "reap_orphaned_mcp_processes.py",
)
assert module_spec is not None
assert module_spec.loader is not None
reaper = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(reaper)


def test_collect_orphaned_mcp_process_ids_requires_dead_parent() -> None:
    all_processes: list[dict[str, object]] = [
        {"ProcessId": 10, "ParentProcessId": 1, "CommandLine": "claude.exe"},
        {
            "ProcessId": 20,
            "ParentProcessId": 10,
            "CommandLine": "npx @bitbonsai/mcpvault@latest vault",
        },
        {
            "ProcessId": 30,
            "ParentProcessId": 99999,
            "CommandLine": "npx @bitbonsai/mcpvault@latest vault",
        },
        {
            "ProcessId": 40,
            "ParentProcessId": 88888,
            "CommandLine": "node app.js",
        },
    ]
    all_orphaned = reaper.collect_orphaned_mcp_process_ids(all_processes)
    assert all_orphaned == [30]


def test_reap_orphaned_mcp_processes_dry_run_lists_without_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_processes: list[dict[str, object]] = [
        {
            "ProcessId": 30,
            "ParentProcessId": 99999,
            "CommandLine": "npx @bitbonsai/mcpvault@latest vault",
        },
    ]
    all_terminated: list[int] = []

    def _fake_list() -> list[dict[str, object]]:
        return all_processes

    def _fake_terminate(process_id: int) -> bool:
        all_terminated.append(process_id)
        return True

    monkeypatch.setattr(reaper.lifecycle, "list_windows_processes", _fake_list)
    monkeypatch.setattr(reaper.lifecycle, "terminate_process_tree", _fake_terminate)
    summary = reaper.reap_orphaned_mcp_processes(is_dry_run=True)
    assert summary["orphan_count"] == 1
    assert summary["orphan_pids"] == [30]
    assert summary["terminated_pids"] == []
    assert all_terminated == []
