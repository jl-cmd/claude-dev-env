"""Run subprocess commands with captured text output for Git materialization."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from config.plan_constants import EXIT_CODE_SUCCESS, UTF8_ENCODING

ProcessRunner = Callable[[list[str], str], "CapturedProcessOutcome"]


@dataclass(frozen=True)
class CapturedProcessOutcome:
    """Captured outcome of one subprocess invocation."""

    exit_code: int
    stdout_text: str
    stderr_text: str

    @property
    def is_success(self) -> bool:
        return self.exit_code == EXIT_CODE_SUCCESS


def run_process(
    all_command: list[str],
    working_directory: str,
) -> CapturedProcessOutcome:
    """Run a command and return exit code plus captured stdout/stderr text.

    Args:
        all_command: argv list (no shell).
        working_directory: Directory the child process runs in.

    Returns:
        CapturedProcessOutcome with exit_code and text streams.
    """
    completed = subprocess.run(
        all_command,
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
        encoding=UTF8_ENCODING,
    )
    return CapturedProcessOutcome(
        exit_code=completed.returncode,
        stdout_text=completed.stdout or "",
        stderr_text=completed.stderr or "",
    )
