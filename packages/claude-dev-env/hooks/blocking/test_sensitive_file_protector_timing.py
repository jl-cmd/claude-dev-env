"""Timing checks for the production PreToolUse dispatcher.

The production dispatcher has a 60-second user-visible timeout in ``hooks.json``.
This test uses a 5-second protection-decision budget. The budget keeps a
Write or Edit decision responsive and leaves 55 seconds before the configured
hard timeout.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

BLOCKING_DIRECTORY = Path(__file__).resolve().parent
DISPATCHER_SCRIPT_PATH = BLOCKING_DIRECTORY / "pre_tool_use_dispatcher.py"

WRITE_TOOL_NAME = "Write"
EDIT_TOOL_NAME = "Edit"
DENY_DECISION = "deny"
DISPATCHER_TIMEOUT_SECONDS = 60
MAXIMUM_SAFE_DISPATCHER_SECONDS = 5
PLACEHOLDER_TEMPLATE_BODY = "API_TOKEN=your-token-here\n"


def _build_sensitive_payload(tool_name: str, file_path: Path) -> dict[str, object]:
    if tool_name == WRITE_TOOL_NAME:
        return {
            "tool_name": tool_name,
            "tool_input": {
                "file_path": str(file_path),
                "content": PLACEHOLDER_TEMPLATE_BODY,
            },
        }
    return {
        "tool_name": tool_name,
        "tool_input": {
            "file_path": str(file_path),
            "old_string": "API_TOKEN=old-token\n",
            "new_string": PLACEHOLDER_TEMPLATE_BODY,
        },
    }


def _run_dispatcher_with_timing(
    payload: dict[str, object],
) -> tuple[subprocess.CompletedProcess[str], float]:
    payload_text = json.dumps(payload)
    started_at = time.monotonic()
    completed_process = subprocess.run(
        [sys.executable, str(DISPATCHER_SCRIPT_PATH)],
        input=payload_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=DISPATCHER_TIMEOUT_SECONDS,
    )
    elapsed_seconds = time.monotonic() - started_at
    return completed_process, elapsed_seconds


@pytest.mark.parametrize("tool_name", (WRITE_TOOL_NAME, EDIT_TOOL_NAME))
def test_dispatcher_denies_sensitive_target_within_protection_budget(
    tmp_path: Path, tool_name: str
) -> None:
    completed_process, elapsed_seconds = _run_dispatcher_with_timing(
        _build_sensitive_payload(tool_name, tmp_path / ".env")
    )

    assert completed_process.returncode == 0, completed_process.stderr
    parsed_payload = json.loads(completed_process.stdout)
    hook_specific_output = parsed_payload["hookSpecificOutput"]
    assert hook_specific_output["permissionDecision"] == DENY_DECISION
    assert elapsed_seconds < MAXIMUM_SAFE_DISPATCHER_SECONDS, (
        f"dispatcher took {elapsed_seconds:.2f}s; the 5s protection-decision budget "
        "keeps Write/Edit responsive and leaves 55s before the hard timeout; "
        f"{MAXIMUM_SAFE_DISPATCHER_SECONDS}s safety boundary"
    )
