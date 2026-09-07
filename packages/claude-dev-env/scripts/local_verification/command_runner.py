from __future__ import annotations

import subprocess
from pathlib import Path

from .config import (
    MISSING_TOOL_ERROR_KIND,
    START_ERROR_KIND,
    TIMEOUT_ERROR_KIND,
    UTF8_ENCODING,
)
from .model import CommandCapture


def run_command(
    all_arguments: tuple[str, ...], check_directory: Path, timeout_seconds: float
) -> CommandCapture:
    """Run a local command and return its captured state.

    Args:
        all_arguments: Command and its arguments.
        check_directory: Working directory for the command.
        timeout_seconds: Wall-clock limit for the command.

    Returns:
        The captured exit code, output, and error kind.
    """
    try:
        completed_process = _run_subprocess(
            all_arguments, check_directory, timeout_seconds
        )
    except FileNotFoundError as error:
        return CommandCapture(None, "", "", MISSING_TOOL_ERROR_KIND, str(error))
    except subprocess.TimeoutExpired as error:
        return _timeout_capture(error)
    except (OSError, ValueError) as error:
        return CommandCapture(None, "", "", START_ERROR_KIND, str(error))
    return _completed_capture(completed_process)


def _timeout_capture(error: subprocess.TimeoutExpired) -> CommandCapture:
    return CommandCapture(
        None,
        _decode_command_text(error.stdout),
        _decode_command_text(error.stderr),
        TIMEOUT_ERROR_KIND,
        "Command exceeded its timeout",
    )


def _completed_capture(
    completed_process: subprocess.CompletedProcess[str],
) -> CommandCapture:
    return CommandCapture(
        completed_process.returncode,
        completed_process.stdout,
        completed_process.stderr,
        None,
        None,
    )


def _run_subprocess(
    all_arguments: tuple[str, ...], check_directory: Path, timeout_seconds: float
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        all_arguments,
        cwd=check_directory,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        encoding=UTF8_ENCODING,
        errors="replace",
        timeout=timeout_seconds,
    )


def _decode_command_text(command_text: str | bytes | None) -> str:
    if command_text is None:
        return ""
    if isinstance(command_text, bytes):
        return command_text.decode(UTF8_ENCODING, errors="replace")
    return command_text
