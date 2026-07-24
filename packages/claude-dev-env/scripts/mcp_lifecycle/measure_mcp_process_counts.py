#!/usr/bin/env python3
"""Measure live mcpvault / playwright / serena / node process counts on Windows.

Prints one JSON object used by the #255 acceptance recipe:

::

    python measure_mcp_process_counts.py

    {
      "mcpvault_cmdline": 0,
      "playwright_mcp": 0,
      "serena": 0,
      "node": 12,
      "total": 400
    }
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from dev_env_scripts_constants.mcp_lifecycle_constants import (  # noqa: E402
    ALL_EMPTY_PROCESS_COUNTS,
    JSON_INDENT_SPACES,
    PROCESS_COUNT_POWERSHELL_COMMAND,
    PROCESS_COUNT_SUBPROCESS_TIMEOUT_SECONDS,
)


def parse_count_payload(payload_text: str) -> dict[str, int]:
    """Parse PowerShell ConvertTo-Json count payload.

    Args:
        payload_text: JSON object text from PowerShell.

    Returns:
        Integer count map; zeros when parse fails.
    """
    if not payload_text.strip():
        return dict(ALL_EMPTY_PROCESS_COUNTS)
    try:
        parsed_payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return dict(ALL_EMPTY_PROCESS_COUNTS)
    if not isinstance(parsed_payload, dict):
        return dict(ALL_EMPTY_PROCESS_COUNTS)
    count_by_name: dict[str, int] = dict(ALL_EMPTY_PROCESS_COUNTS)
    for each_key in ALL_EMPTY_PROCESS_COUNTS:
        raw_count = parsed_payload.get(each_key, 0)
        if isinstance(raw_count, bool):
            count_by_name[each_key] = int(raw_count)
            continue
        if isinstance(raw_count, int):
            count_by_name[each_key] = raw_count
            continue
        if isinstance(raw_count, float):
            count_by_name[each_key] = int(raw_count)
            continue
        try:
            count_by_name[each_key] = int(str(raw_count))
        except (TypeError, ValueError):
            count_by_name[each_key] = 0
    return count_by_name


def measure_mcp_process_counts() -> dict[str, int]:
    """Sample live MCP-related process counts on Windows.

    Returns:
        Count map. Non-Windows hosts return zeros.
    """
    if sys.platform != "win32":
        return dict(ALL_EMPTY_PROCESS_COUNTS)
    try:
        completed_process = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                PROCESS_COUNT_POWERSHELL_COMMAND,
            ],
            capture_output=True,
            text=True,
            timeout=PROCESS_COUNT_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return dict(ALL_EMPTY_PROCESS_COUNTS)
    if completed_process.returncode != 0:
        return dict(ALL_EMPTY_PROCESS_COUNTS)
    return parse_count_payload(completed_process.stdout)


def main() -> int:
    """Print JSON counts to stdout.

    Returns:
        Process exit code.
    """
    count_by_name = measure_mcp_process_counts()
    print(json.dumps(count_by_name, indent=JSON_INDENT_SPACES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
