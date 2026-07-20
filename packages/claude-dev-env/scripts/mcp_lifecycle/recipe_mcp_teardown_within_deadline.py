#!/usr/bin/env python3
"""Synthetic recipe: register a host, spawn an MCP-like child, tear down <60s.

Proves the SessionEnd teardown path terminates a tracked MCP-marker process
tree that descends from a registered host PID within the acceptance deadline.

::

    python recipe_mcp_teardown_within_deadline.py
    # prints JSON: {"ok": true, "elapsed_seconds": ..., "deadline_seconds": 60}
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_package_dir = str(Path(__file__).resolve().parent)
_scripts_dir = str(Path(__file__).resolve().parent.parent)
if _package_dir not in sys.path:
    sys.path.insert(0, _package_dir)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from load_mcp_session_lifecycle import load_mcp_session_lifecycle_module  # noqa: E402

from dev_env_scripts_constants.mcp_lifecycle_constants import (  # noqa: E402
    ELAPSED_SECONDS_PRECISION,
    JSON_INDENT_SPACES,
    MCP_MARKER_LABEL,
    RECIPE_CHILD_KILL_WAIT_SECONDS,
    RECIPE_CHILD_SETTLE_SECONDS,
    RECIPE_POLL_INTERVAL_SECONDS,
    SESSION_ID_FOR_RECIPE,
    TEARDOWN_DEADLINE_SECONDS,
)

lifecycle = load_mcp_session_lifecycle_module()


def _spawn_mcp_marker_child() -> subprocess.Popen[bytes]:
    if sys.platform == "win32":
        return subprocess.Popen(
            [
                "cmd.exe",
                "/d",
                "/s",
                "/c",
                f"ping -n 120 127.0.0.1 >nul & rem {MCP_MARKER_LABEL}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return subprocess.Popen(
        [
            "bash",
            "-c",
            f"exec -a {MCP_MARKER_LABEL} sleep 120",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _child_is_alive(process_id: int) -> bool:
    if process_id <= 0:
        return False
    if sys.platform == "win32":
        completed_process = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-Process -Id {process_id} -ErrorAction SilentlyContinue | "
                "Select-Object -ExpandProperty Id",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(process_id) in completed_process.stdout
    try:
        os.kill(process_id, 0)
    except OSError:
        return False
    return True


def run_recipe() -> dict[str, object]:
    """Execute the synthetic teardown acceptance recipe.

    Returns:
        Summary dictionary with ok/elapsed_seconds/deadline_seconds.
    """
    host_pid = os.getpid()
    with tempfile.TemporaryDirectory() as temporary_directory:
        registry_directory = temporary_directory
        lifecycle.write_host_pid_registry(
            session_id=SESSION_ID_FOR_RECIPE,
            host_pid=host_pid,
            registry_directory=registry_directory,
        )
        child_process = _spawn_mcp_marker_child()
        child_process_id = child_process.pid
        time.sleep(RECIPE_CHILD_SETTLE_SECONDS)
        started_at = time.monotonic()
        if sys.platform == "win32":
            all_processes = lifecycle.list_windows_processes()
        else:
            all_processes = [
                {
                    "ProcessId": child_process_id,
                    "ParentProcessId": host_pid,
                    "CommandLine": f"{MCP_MARKER_LABEL} sleep",
                }
            ]
        lifecycle.run_session_lifecycle(
            payload_by_field={
                "session_id": SESSION_ID_FOR_RECIPE,
                "hook_event_name": "SessionEnd",
            },
            host_pid=host_pid,
            registry_directory=registry_directory,
            all_processes=all_processes,
        )
        deadline_seconds = TEARDOWN_DEADLINE_SECONDS
        is_gone = False
        while time.monotonic() - started_at < deadline_seconds:
            if not _child_is_alive(child_process_id):
                is_gone = True
                break
            time.sleep(RECIPE_POLL_INTERVAL_SECONDS)
        if child_process.poll() is None:
            child_process.kill()
            child_process.wait(timeout=RECIPE_CHILD_KILL_WAIT_SECONDS)
        elapsed_seconds = round(
            time.monotonic() - started_at,
            ELAPSED_SECONDS_PRECISION,
        )
        return {
            "ok": is_gone and elapsed_seconds <= deadline_seconds,
            "elapsed_seconds": elapsed_seconds,
            "deadline_seconds": deadline_seconds,
            "child_pid": child_process_id,
            "host_pid": host_pid,
            "platform": sys.platform,
        }


def main() -> int:
    """Run the recipe and print JSON.

    Returns:
        0 when teardown met the deadline, else 1.
    """
    recipe_summary = run_recipe()
    print(json.dumps(recipe_summary, indent=JSON_INDENT_SPACES))
    return 0 if recipe_summary.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
