"""Behavior tests for git_find_handle_guard process killer."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_GUARDS_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _GUARDS_DIR.parent.parent
for each_sys_path_entry in (str(_GUARDS_DIR), str(_HOOKS_ROOT)):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

_HOOK_SPEC = importlib.util.spec_from_file_location(
    "git_find_handle_guard",
    _GUARDS_DIR / "git_find_handle_guard.py",
)
assert _HOOK_SPEC is not None
assert _HOOK_SPEC.loader is not None
guard = importlib.util.module_from_spec(_HOOK_SPEC)
sys.modules["git_find_handle_guard"] = guard
_HOOK_SPEC.loader.exec_module(guard)

GitFindProcessSnapshot = guard.GitFindProcessSnapshot


def _git_find(
    process_id: int,
    handle_count: int,
    command_line: str = "find / -name foo",
) -> GitFindProcessSnapshot:
    return GitFindProcessSnapshot(
        process_id=process_id,
        handle_count=handle_count,
        executable_path=r"C:\Program Files\Git\usr\bin\find.exe",
        command_line=command_line,
    )


class TestIsGitUsrBinFind:
    def test_accepts_git_usr_bin_find(self) -> None:
        assert guard.is_git_usr_bin_find(
            r"C:\Program Files\Git\usr\bin\find.exe"
        )

    def test_accepts_forward_slash_form(self) -> None:
        assert guard.is_git_usr_bin_find(
            "C:/Program Files/Git/usr/bin/find.exe"
        )

    def test_rejects_system32_find(self) -> None:
        assert not guard.is_git_usr_bin_find(
            r"C:\Windows\System32\find.exe"
        )

    def test_rejects_empty_path(self) -> None:
        assert not guard.is_git_usr_bin_find("")


class TestParseFindProcessQueryPayload:
    def test_parses_single_object(self) -> None:
        all_snapshots = guard.parse_find_process_query_payload(
            {
                "ProcessId": 87468,
                "HandleCount": 3_379_540,
                "ExecutablePath": r"C:\Program Files\Git\usr\bin\find.exe",
                "CommandLine": r'"C:\Program Files\Git\usr\bin\find.exe" / -name nest_asyncio.py',
            }
        )
        assert len(all_snapshots) == 1
        assert all_snapshots[0].process_id == 87468
        assert all_snapshots[0].handle_count == 3_379_540

    def test_filters_non_git_find(self) -> None:
        all_snapshots = guard.parse_find_process_query_payload(
            [
                {
                    "ProcessId": 1,
                    "HandleCount": 5000,
                    "ExecutablePath": r"C:\Windows\System32\find.exe",
                    "CommandLine": "find /i foo",
                }
            ]
        )
        assert all_snapshots == []

    def test_parses_list_of_rows(self) -> None:
        all_snapshots = guard.parse_find_process_query_payload(
            [
                {
                    "ProcessId": 10,
                    "HandleCount": 100,
                    "ExecutablePath": r"C:\Program Files\Git\usr\bin\find.exe",
                    "CommandLine": "find . -name a",
                },
                {
                    "ProcessId": 20,
                    "HandleCount": 2500,
                    "ExecutablePath": r"C:\Program Files\Git\usr\bin\find.exe",
                    "CommandLine": "find / -name b",
                },
            ]
        )
        assert [each.process_id for each in all_snapshots] == [10, 20]


class TestSelectRunaway:
    def test_selects_only_over_threshold(self) -> None:
        all_snapshots = [
            _git_find(1, 100),
            _git_find(2, 2001),
            _git_find(3, 2000),
        ]
        all_runaways = guard.select_runaway_git_find_processes(
            all_snapshots,
            handle_threshold=2000,
        )
        assert [each.process_id for each in all_runaways] == [2]


class TestRunGuardSweep:
    def test_dry_run_reports_without_killing(self) -> None:
        all_live = [_git_find(99, 50_000)]
        all_killed: list[int] = []

        def _query() -> list[GitFindProcessSnapshot]:
            return list(all_live)

        def _total() -> int:
            return 3_500_000

        def _terminate(process_id: int) -> bool:
            all_killed.append(process_id)
            return True

        sweep_report = guard.run_guard_sweep(
            handle_threshold=2000,
            is_dry_run=True,
            query_processes=_query,
            query_total_handles=_total,
            terminate=_terminate,
        )
        assert sweep_report.all_killed_process_ids == []
        assert all_killed == []
        assert sweep_report.total_handles_before == 3_500_000
        assert len(sweep_report.all_git_find_before) == 1

    def test_live_kill_records_before_after_counters(self) -> None:
        all_live = [_git_find(87468, 3_379_540)]
        all_killed: list[int] = []
        total_handles = {"count": 3_550_000}

        def _query() -> list[GitFindProcessSnapshot]:
            return [
                each_snapshot
                for each_snapshot in all_live
                if each_snapshot.process_id not in all_killed
            ]

        def _total() -> int:
            return total_handles["count"]

        def _terminate(process_id: int) -> bool:
            all_killed.append(process_id)
            total_handles["count"] = 180_000
            return True

        sweep_report = guard.run_guard_sweep(
            handle_threshold=2000,
            is_dry_run=False,
            query_processes=_query,
            query_total_handles=_total,
            terminate=_terminate,
        )
        assert sweep_report.all_killed_process_ids == [87468]
        assert sweep_report.total_handles_before == 3_550_000
        assert sweep_report.total_handles_after == 180_000
        assert sweep_report.all_git_find_after == []
        assert all_killed == [87468]

    def test_below_threshold_is_not_killed(self) -> None:
        all_live = [_git_find(5, 500)]
        all_killed: list[int] = []

        sweep_report = guard.run_guard_sweep(
            handle_threshold=2000,
            is_dry_run=False,
            query_processes=lambda: list(all_live),
            query_total_handles=lambda: 100_000,
            terminate=lambda process_id: all_killed.append(process_id) or True,
        )
        assert sweep_report.all_killed_process_ids == []
        assert all_killed == []


def test_report_as_jsonable_is_serializable() -> None:
    sweep_report = guard.run_guard_sweep(
        handle_threshold=2000,
        is_dry_run=True,
        query_processes=lambda: [_git_find(1, 3000)],
        query_total_handles=lambda: 1_000_000,
        terminate=lambda _process_id: True,
    )
    jsonable = guard.report_as_jsonable(sweep_report)
    encoded = json.dumps(jsonable)
    decoded = json.loads(encoded)
    assert decoded["handle_threshold"] == 2000
    assert decoded["all_git_find_before"][0]["process_id"] == 1
    assert decoded["all_killed_process_ids"] == []
