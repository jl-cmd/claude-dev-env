#!/usr/bin/env python3
"""Stop-hook dispatcher that hosts the five Stop-chain hooks in one process.

Reads the Stop payload from stdin once, runs each hosted hook in registration
order via the shared hosted-hook runner, and emits the first block decision the
chain produced. Later hooks still run so side-effect hooks (the log extractor
wrapper) fire even when an earlier hook blocked. A single hosted hook crash
fails open and does not suppress the remaining hooks.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import _path_setup  # noqa: F401

from hooks_constants.hosted_hook_runner import HostedHookRun, run_hook_capturing_output
from hooks_constants.stop_dispatcher_constants import (
    ALL_STOP_HOSTED_HOOK_PATHS,
    BLOCK_DECISION,
    DECISION_KEY,
)


def _resolve_hook_script_path(relative_path: str) -> str:
    """Resolve a hooks/-relative path to an absolute script path."""
    hooks_root = Path(__file__).resolve().parent.parent
    return str(hooks_root / relative_path)


def _is_block_decision(stdout_text: str) -> bool:
    """Return True when stdout carries a Stop decision of block."""
    stripped_text = stdout_text.strip()
    if not stripped_text:
        return False
    try:
        parsed_output = json.loads(stripped_text)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed_output, dict):
        return False
    return parsed_output.get(DECISION_KEY) == BLOCK_DECISION


def select_first_block_stdout(all_runs: list[HostedHookRun]) -> str:
    """Return the first non-crashed block stdout, or empty when none blocked."""
    for each_run in all_runs:
        if each_run.did_crash:
            continue
        if _is_block_decision(each_run.captured_stdout):
            return each_run.captured_stdout.strip()
    return ""


def dispatch(payload_text: str) -> None:
    """Run every Stop hosted hook and emit the first block decision if any."""
    all_runs: list[HostedHookRun] = []
    for each_relative_path in ALL_STOP_HOSTED_HOOK_PATHS:
        script_path = _resolve_hook_script_path(each_relative_path)
        hook_run = run_hook_capturing_output(script_path, payload_text)
        all_runs.append(hook_run)
    block_stdout = select_first_block_stdout(all_runs)
    if block_stdout:
        sys.stdout.write(block_stdout + "\n")
        sys.stdout.flush()


def main() -> None:
    """Read stdin once and dispatch the Stop hosted-hook chain."""
    payload_text = sys.stdin.read()
    if not payload_text.strip():
        sys.exit(0)
    try:
        json.loads(payload_text)
    except json.JSONDecodeError:
        sys.exit(0)
    dispatch(payload_text)
    sys.exit(0)


if __name__ == "__main__":
    main()
