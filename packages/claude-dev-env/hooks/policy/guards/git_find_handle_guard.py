#!/usr/bin/env python3
"""Kill runaway Git usr\\bin\\find.exe processes when Handles exceed the threshold.

Operator threshold is 2000 handles (issue #253). Live incidents have climbed past
1M–3M handles on a single find over `/`. This module:

- enumerates find.exe processes whose ExecutablePath is Git usr\\bin\\find.exe
- kills those whose HandleCount is greater than HANDLE_KILL_THRESHOLD
- prints before/after counters as JSON for acceptance evidence

Callable as a SessionStart hook (one-shot, stdin JSON ignored for policy) or as a
CLI:

  python git_find_handle_guard.py
  python git_find_handle_guard.py --dry-run
  python git_find_handle_guard.py --watch
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.find_filesystem_walk_constants import (  # noqa: E402
    ALL_CLI_MODE_FLAGS,
    CLI_DESCRIPTION_TEMPLATE,
    CLI_DRY_RUN_FLAG,
    CLI_DRY_RUN_HELP,
    CLI_THRESHOLD_EQUALS_PREFIX,
    CLI_THRESHOLD_FLAG,
    CLI_THRESHOLD_HELP_TEMPLATE,
    CLI_WATCH_FLAG,
    CLI_WATCH_HELP_TEMPLATE,
    FIND_PROCESS_NAME,
    FIND_PROCESS_QUERY_SCRIPT,
    GIT_FIND_PATH_SUFFIX,
    GUARD_HOOK_SCRIPT_NAME,
    HANDLE_KILL_THRESHOLD,
    POWERSHELL_COMMAND_FLAG,
    POWERSHELL_EXECUTABLE_NAME,
    POWERSHELL_NO_PROFILE_FLAG,
    TASKKILL_EXECUTABLE_NAME,
    TASKKILL_FORCE_FLAG,
    TASKKILL_PID_FLAG,
    TOTAL_HANDLE_COUNTER_PATH,
    TOTAL_HANDLE_COUNTER_QUERY_TEMPLATE,
    WATCH_POLL_INTERVAL_SECONDS,
)


@dataclass(frozen=True)
class GitFindProcessSnapshot:
    """One live Git find.exe process and its handle count.

    Attributes:
        process_id: OS process id.
        handle_count: Open handles reported by the process object.
        executable_path: Full path to the find binary.
        command_line: Full command line when available.
    """

    process_id: int
    handle_count: int
    executable_path: str
    command_line: str


@dataclass(frozen=True)
class GuardSweepReport:
    """Before/after counters from one kill sweep.

    Attributes:
        handle_threshold: Threshold used for this sweep.
        is_dry_run: True when no process was terminated.
        total_handles_before: System _Total handle count before the sweep.
        total_handles_after: System _Total handle count after the sweep.
        all_git_find_before: Git find snapshots before the sweep.
        all_killed_process_ids: Process ids terminated this sweep.
        all_git_find_after: Git find snapshots after the sweep.
    """

    handle_threshold: int
    is_dry_run: bool
    total_handles_before: int
    total_handles_after: int
    all_git_find_before: list[GitFindProcessSnapshot]
    all_killed_process_ids: list[int]
    all_git_find_after: list[GitFindProcessSnapshot]


def normalize_executable_path(executable_path: str) -> str:
    """Lowercase and normalize slashes for path suffix comparison.

    Args:
        executable_path: Raw ExecutablePath from CIM or an empty string.

    Returns:
        Lowercased path with backslashes.
    """
    return executable_path.replace("/", "\\").lower()


def is_git_usr_bin_find(executable_path: str) -> bool:
    """Return True when the path is Git's usr\\bin\\find.exe.

    ::

        is_git_usr_bin_find(r'C:\\Program Files\\Git\\usr\\bin\\find.exe')
        ok:   True
        flag: False for C:\\Windows\\System32\\find.exe

    Args:
        executable_path: Full path to a find binary.

    Returns:
        True when the path ends with the Git usr\\bin\\find.exe suffix.
    """
    if not executable_path:
        return False
    return normalize_executable_path(executable_path).endswith(GIT_FIND_PATH_SUFFIX)


def parse_find_process_query_payload(
    query_payload: object,
) -> list[GitFindProcessSnapshot]:
    """Parse ConvertTo-Json output from the find process query.

    Args:
        query_payload: Decoded JSON (dict, list, or other).

    Returns:
        Snapshots for every row that looks like a Git find process.
    """
    if query_payload is None:
        return []
    all_rows: list[object]
    if isinstance(query_payload, list):
        all_rows = query_payload
    elif isinstance(query_payload, dict):
        all_rows = [query_payload]
    else:
        return []

    all_snapshots: list[GitFindProcessSnapshot] = []
    for each_row in all_rows:
        if not isinstance(each_row, dict):
            continue
        raw_process_id = each_row.get("ProcessId", 0)
        raw_handle_count = each_row.get("HandleCount", 0)
        raw_executable_path = each_row.get("ExecutablePath", "")
        raw_command_line = each_row.get("CommandLine", "")
        process_id = int(raw_process_id) if isinstance(raw_process_id, (int, float, str)) else 0
        handle_count = (
            int(raw_handle_count) if isinstance(raw_handle_count, (int, float, str)) else 0
        )
        executable_path = (
            raw_executable_path if isinstance(raw_executable_path, str) else ""
        )
        command_line = raw_command_line if isinstance(raw_command_line, str) else ""
        if process_id <= 0:
            continue
        if not is_git_usr_bin_find(executable_path):
            continue
        all_snapshots.append(
            GitFindProcessSnapshot(
                process_id=process_id,
                handle_count=handle_count,
                executable_path=executable_path,
                command_line=command_line,
            )
        )
    return all_snapshots


def query_git_find_processes_via_powershell() -> list[GitFindProcessSnapshot]:
    """Query live Git find.exe processes through PowerShell CIM + Get-Process.

    Returns:
        Snapshots for every live Git usr\\bin\\find.exe process.
    """
    completed = subprocess.run(
        [
            POWERSHELL_EXECUTABLE_NAME,
            POWERSHELL_NO_PROFILE_FLAG,
            POWERSHELL_COMMAND_FLAG,
            FIND_PROCESS_QUERY_SCRIPT,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_text = completed.stdout.strip()
    if not stdout_text:
        return []
    try:
        query_payload = json.loads(stdout_text)
    except json.JSONDecodeError:
        return []
    return parse_find_process_query_payload(query_payload)


def query_total_handle_count() -> int:
    """Return the system _Total handle count, or 0 when the counter is unavailable.

    Returns:
        Integer handle count from the Process(_Total) counter.
    """
    completed = subprocess.run(
        [
            POWERSHELL_EXECUTABLE_NAME,
            POWERSHELL_NO_PROFILE_FLAG,
            POWERSHELL_COMMAND_FLAG,
            TOTAL_HANDLE_COUNTER_QUERY_TEMPLATE.format(
                counter_path=TOTAL_HANDLE_COUNTER_PATH
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_text = completed.stdout.strip()
    if not stdout_text:
        return 0
    try:
        return int(float(stdout_text))
    except ValueError:
        return 0


def select_runaway_git_find_processes(
    all_snapshots: list[GitFindProcessSnapshot],
    handle_threshold: int,
) -> list[GitFindProcessSnapshot]:
    """Return Git find processes whose handle count exceeds the threshold.

    Args:
        all_snapshots: Live Git find snapshots.
        handle_threshold: Inclusive lower bound that triggers a kill.

    Returns:
        Snapshots with handle_count greater than handle_threshold.
    """
    return [
        each_snapshot
        for each_snapshot in all_snapshots
        if each_snapshot.handle_count > handle_threshold
    ]


def terminate_process(process_id: int) -> bool:
    """Terminate one process by id. Returns True when the kill was issued.

    On Windows uses ``taskkill /F /PID`` so a stuck Git find.exe with millions of
    handles is force-stopped rather than left as a zero-handle zombie after a
    soft SIGTERM. Other platforms use SIGTERM.

    Args:
        process_id: Target OS process id.

    Returns:
        True when termination was attempted successfully; False on failure.
    """
    if sys.platform == "win32":
        completed = subprocess.run(
            [
                TASKKILL_EXECUTABLE_NAME,
                TASKKILL_FORCE_FLAG,
                TASKKILL_PID_FLAG,
                str(process_id),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode == 0
    try:
        os.kill(process_id, signal.SIGTERM)
        return True
    except OSError:
        return False


def run_guard_sweep(
    *,
    handle_threshold: int,
    is_dry_run: bool,
    query_processes: Callable[[], list[GitFindProcessSnapshot]],
    query_total_handles: Callable[[], int],
    terminate: Callable[[int], bool],
) -> GuardSweepReport:
    """Enumerate runaway Git find processes and kill them when not dry-run.

    ::

        report = run_guard_sweep(
            handle_threshold=2000,
            is_dry_run=True,
            query_processes=query_git_find_processes_via_powershell,
            query_total_handles=query_total_handle_count,
            terminate=terminate_process,
        )
        ok:   report.all_killed_process_ids == []
        flag: live kill when is_dry_run is False and handles exceed threshold

    Args:
        handle_threshold: Kill when HandleCount is greater than this value.
        is_dry_run: When True, report only — never terminate.
        query_processes: Process enumerator (PowerShell query or test double).
        query_total_handles: Total-handle counter (or test double).
        terminate: Process terminator (or test double).

    Returns:
        GuardSweepReport with before/after counters and killed process ids.
    """
    total_handles_before = query_total_handles()
    all_git_find_before = query_processes()
    all_runaways = select_runaway_git_find_processes(
        all_git_find_before,
        handle_threshold=handle_threshold,
    )
    all_killed_process_ids: list[int] = []
    if not is_dry_run:
        for each_runaway in all_runaways:
            if terminate(each_runaway.process_id):
                all_killed_process_ids.append(each_runaway.process_id)

    all_git_find_after = query_processes()
    total_handles_after = query_total_handles()
    return GuardSweepReport(
        handle_threshold=handle_threshold,
        is_dry_run=is_dry_run,
        total_handles_before=total_handles_before,
        total_handles_after=total_handles_after,
        all_git_find_before=all_git_find_before,
        all_killed_process_ids=all_killed_process_ids,
        all_git_find_after=all_git_find_after,
    )


def report_as_jsonable(report: GuardSweepReport) -> dict[str, object]:
    """Convert a GuardSweepReport into a JSON-serializable dict.

    Args:
        report: Sweep report to serialize.

    Returns:
        Plain dict with nested process snapshots as dicts.
    """
    return {
        "handle_threshold": report.handle_threshold,
        "is_dry_run": report.is_dry_run,
        "total_handles_before": report.total_handles_before,
        "total_handles_after": report.total_handles_after,
        "all_git_find_before": [asdict(each) for each in report.all_git_find_before],
        "all_killed_process_ids": list(report.all_killed_process_ids),
        "all_git_find_after": [asdict(each) for each in report.all_git_find_after],
        "guard": GUARD_HOOK_SCRIPT_NAME,
        "find_process_name": FIND_PROCESS_NAME,
    }


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=CLI_DESCRIPTION_TEMPLATE.format(threshold=HANDLE_KILL_THRESHOLD)
    )
    parser.add_argument(
        CLI_WATCH_FLAG,
        action="store_true",
        help=CLI_WATCH_HELP_TEMPLATE.format(poll_seconds=WATCH_POLL_INTERVAL_SECONDS),
    )
    parser.add_argument(
        CLI_DRY_RUN_FLAG,
        action="store_true",
        help=CLI_DRY_RUN_HELP,
    )
    parser.add_argument(
        CLI_THRESHOLD_FLAG,
        type=int,
        default=HANDLE_KILL_THRESHOLD,
        help=CLI_THRESHOLD_HELP_TEMPLATE.format(threshold=HANDLE_KILL_THRESHOLD),
    )
    return parser


def _print_sweep_report(sweep_report: GuardSweepReport) -> None:
    print(json.dumps(report_as_jsonable(sweep_report)))
    sys.stdout.flush()


def argv_requests_cli_mode(all_arguments: list[str]) -> bool:
    """Return True when argv carries a CLI mode flag or any non-empty args.

    Args:
        all_arguments: sys.argv[1:] style argument list.

    Returns:
        True when the process should run as a CLI rather than SessionStart.
    """
    if not all_arguments:
        return False
    for each_argument in all_arguments:
        if each_argument in ALL_CLI_MODE_FLAGS:
            return True
        if each_argument.startswith(CLI_THRESHOLD_EQUALS_PREFIX):
            return True
    return True


def run_cli(all_argv: list[str] | None = None) -> int:
    """CLI entry: run one sweep or a watch loop; print JSON reports to stdout.

    Args:
        all_argv: Optional argv override (excluding the script name).

    Returns:
        Process exit code (0 on success).
    """
    parser = _build_argument_parser()
    parsed_arguments = parser.parse_args(all_argv)
    is_dry_run = bool(parsed_arguments.dry_run)
    handle_threshold = int(parsed_arguments.threshold)
    should_watch = bool(parsed_arguments.watch)

    while True:
        sweep_report = run_guard_sweep(
            handle_threshold=handle_threshold,
            is_dry_run=is_dry_run,
            query_processes=query_git_find_processes_via_powershell,
            query_total_handles=query_total_handle_count,
            terminate=terminate_process,
        )
        _print_sweep_report(sweep_report)
        if not should_watch:
            return 0
        time.sleep(WATCH_POLL_INTERVAL_SECONDS)


def main() -> None:
    """SessionStart / CLI entry point.

    When argv carries CLI flags, run the CLI. Otherwise run one live sweep
    (SessionStart path) and exit 0 so the hook never blocks session start.
    """
    if argv_requests_cli_mode(sys.argv[1:]):
        sys.exit(run_cli(sys.argv[1:]))
    sweep_report = run_guard_sweep(
        handle_threshold=HANDLE_KILL_THRESHOLD,
        is_dry_run=False,
        query_processes=query_git_find_processes_via_powershell,
        query_total_handles=query_total_handle_count,
        terminate=terminate_process,
    )
    _print_sweep_report(sweep_report)
    sys.exit(0)


if __name__ == "__main__":
    main()
