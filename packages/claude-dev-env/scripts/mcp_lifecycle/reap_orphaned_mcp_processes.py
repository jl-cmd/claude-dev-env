#!/usr/bin/env python3
"""Reap MCP-marker processes whose parent PID is no longer alive.

Safe cleanup for spawn-without-reap leftovers after a host exit that never
ran SessionEnd. Only terminates process trees whose ParentProcessId is missing
from the live process table — never kills MCP children of a still-running host.

::

    python reap_orphaned_mcp_processes.py --dry-run
    python reap_orphaned_mcp_processes.py --apply
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

_package_dir = str(Path(__file__).resolve().parent)
_scripts_dir = str(Path(__file__).resolve().parent.parent)
if _package_dir not in sys.path:
    sys.path.insert(0, _package_dir)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from load_mcp_session_lifecycle import load_mcp_session_lifecycle_module  # noqa: E402

from dev_env_scripts_constants.mcp_lifecycle_constants import (  # noqa: E402
    JSON_INDENT_SPACES,
)

lifecycle = load_mcp_session_lifecycle_module()


def collect_orphaned_mcp_process_ids(
    all_processes: list[dict[str, object]],
) -> list[int]:
    """Return MCP process ids whose parent is not in the live process table.

    Args:
        all_processes: Live process rows.

    Returns:
        Deduplicated orphan MCP process ids.
    """
    all_live_process_ids = {
        each_process.get("ProcessId")
        for each_process in all_processes
        if isinstance(each_process.get("ProcessId"), int)
    }
    all_orphaned_process_ids: list[int] = []
    for each_process in all_processes:
        process_id = each_process.get("ProcessId")
        parent_process_id = each_process.get("ParentProcessId")
        command_line = each_process.get("CommandLine")
        if not isinstance(process_id, int):
            continue
        if not isinstance(parent_process_id, int):
            continue
        command_line_text = command_line if isinstance(command_line, str) else ""
        if not lifecycle.command_line_matches_mcp_server(command_line_text):
            continue
        if parent_process_id in all_live_process_ids:
            continue
        all_orphaned_process_ids.append(process_id)
    return list(dict.fromkeys(all_orphaned_process_ids))


def reap_orphaned_mcp_processes(*, is_dry_run: bool) -> dict[str, object]:
    """Find and optionally terminate orphaned MCP process trees.

    Args:
        is_dry_run: When True, list only.

    Returns:
        Summary with orphan pids and whether terminate ran.
    """
    all_processes = lifecycle.list_windows_processes()
    all_orphaned_process_ids = collect_orphaned_mcp_process_ids(all_processes)
    all_terminated_process_ids: list[int] = []
    if not is_dry_run and all_orphaned_process_ids:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(all_orphaned_process_ids)
        ) as executor:
            all_terminate_succeeded_flags = list(
                executor.map(
                    lifecycle.terminate_process_tree, all_orphaned_process_ids
                )
            )
        all_terminated_process_ids = [
            each_process_id
            for each_process_id, each_terminated in zip(
                all_orphaned_process_ids, all_terminate_succeeded_flags
            )
            if each_terminated
        ]
    return {
        "orphan_count": len(all_orphaned_process_ids),
        "orphan_pids": all_orphaned_process_ids,
        "terminated_pids": all_terminated_process_ids,
        "dry_run": is_dry_run,
    }


def main() -> int:
    """CLI entry.

    Returns:
        Exit code.
    """
    argument_parser = argparse.ArgumentParser(
        description="Reap MCP processes whose parent host is already dead."
    )
    mode_group = argument_parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--dry-run", action="store_true")
    mode_group.add_argument("--apply", action="store_true")
    parsed_arguments = argument_parser.parse_args()
    is_dry_run = bool(parsed_arguments.dry_run)
    summary = reap_orphaned_mcp_processes(is_dry_run=is_dry_run)
    print(json.dumps(summary, indent=JSON_INDENT_SPACES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
