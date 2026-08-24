"""Shared entrypoint helpers for code-rules enforcer behavior tests."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


_ENFORCER_SCRIPT_PATH = Path(__file__).with_name("code_rules_enforcer.py")


def build_write_payload(file_path: str, content: str) -> str:
    """Build the JSON payload sent by a Write tool call."""
    return json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
        }
    )


def run_serialized_payload_entrypoint(
    entrypoint: Callable[[list[str]], None],
    serialized_payload: str,
) -> tuple[str, int | None]:
    """Run a callable hook entrypoint with a serialized stdin payload."""
    input_stream = io.StringIO(serialized_payload)
    captured_stream = io.StringIO()
    original_stdin = sys.stdin
    original_stdout = sys.stdout
    exit_code: int | None = None
    try:
        sys.stdin = input_stream
        sys.stdout = captured_stream
        entrypoint([])
    except SystemExit as each_exit:
        raw_code = each_exit.code
        exit_code = raw_code if isinstance(raw_code, int) else None
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout
    return captured_stream.getvalue(), exit_code


def run_write_entrypoint(
    entrypoint: Callable[[list[str]], None],
    file_path: str,
    content: str,
) -> tuple[str, int]:
    """Drive a real hook entrypoint with a Write payload and capture stdout."""
    captured_stdout, exit_code = run_serialized_payload_entrypoint(
        entrypoint, build_write_payload(file_path, content)
    )
    return captured_stdout, int(exit_code or 0)


def run_enforcer_cli(
    script_path: Path,
    all_arguments: list[str],
    extra_environment_by_name: dict[str, str] | None,
) -> subprocess.CompletedProcess[str]:
    """Run an enforcer script through its real command-line entrypoint."""
    subprocess_environment: dict[str, str] | None = None
    if extra_environment_by_name is not None:
        subprocess_environment = os.environ.copy()
        subprocess_environment.update(extra_environment_by_name)
    return subprocess.run(
        [sys.executable, str(script_path), *all_arguments],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        env=subprocess_environment,
    )


def run_precheck(
    candidate_path: Path,
    target_path: str,
    extra_environment_by_name: dict[str, str] | None,
) -> subprocess.CompletedProcess[str]:
    """Run an enforcer script through its real precheck command."""
    return run_enforcer_cli(
        _ENFORCER_SCRIPT_PATH,
        ["--check", str(candidate_path), "--as", target_path],
        extra_environment_by_name,
    )
