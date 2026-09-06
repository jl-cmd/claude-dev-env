"""Start automatic local verification for a supported native Git event."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Mapping

from git_hooks_constants.verification_notice_constants import (
    ALL_NOTICE_EVENTS,
    ALL_RUNNER_FIELDS,
    AUTOMATIC_ADVISORY_CLI_FILE_NAME,
    AUTOMATIC_ADVISORY_DIRECTORY_NAME,
    CREATE_NO_WINDOW_ATTRIBUTE,
    EXECUTOR_DIRECTORY_NAME,
    GIT_DIRECTORY_NAME,
    JSON_ENCODING,
    LOCAL_VERIFICATION_DIRECTORY_NAME,
    RUNNER_FILE_NAME,
    RUNNER_PYTHON_FIELD,
    RUNNER_SETTINGS_FIELD,
    TARGET_REPOSITORY_REMOTE,
    WINDOWS_PLATFORM,
)
from verification_notice_context import VerificationNoticeContext


def start_automatic_advisory(context: VerificationNoticeContext) -> None:
    """Start the detached advisory poller when native metadata is valid."""
    if context.repository_remote != TARGET_REPOSITORY_REMOTE:
        return
    if context.event not in ALL_NOTICE_EVENTS:
        return
    runner_configuration = load_runner_configuration(context)
    if runner_configuration is None:
        return
    python_path, settings_path = runner_configuration
    advisory_cli_path = (
        Path(__file__).resolve().parents[2]
        / EXECUTOR_DIRECTORY_NAME
        / AUTOMATIC_ADVISORY_DIRECTORY_NAME
        / AUTOMATIC_ADVISORY_CLI_FILE_NAME
    )
    try:
        _launch_advisory(
            context,
            python_path,
            settings_path,
            advisory_cli_path,
        )
    except (OSError, subprocess.SubprocessError):
        return


def _launch_advisory(
    context: VerificationNoticeContext,
    python_path: str,
    settings_path: str,
    advisory_cli_path: Path,
) -> None:
    subprocess.Popen(
        [python_path, str(advisory_cli_path), "--settings", settings_path, "--start"],
        cwd=context.repository_root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_windows_creation_flags(),
    )


def load_runner_configuration(
    context: VerificationNoticeContext,
) -> tuple[str, str] | None:
    git_directory = context.git_directory or context.repository_root / GIT_DIRECTORY_NAME
    runner_path = git_directory / LOCAL_VERIFICATION_DIRECTORY_NAME / RUNNER_FILE_NAME
    try:
        runner_document = json.loads(runner_path.read_text(encoding=JSON_ENCODING))
    except (OSError, UnicodeError, ValueError):
        return None
    if not isinstance(runner_document, Mapping):
        return None
    if set(runner_document) != ALL_RUNNER_FIELDS:
        return None
    python_path = runner_document.get(RUNNER_PYTHON_FIELD)
    settings_path = runner_document.get(RUNNER_SETTINGS_FIELD)
    if not isinstance(python_path, str) or not python_path.strip():
        return None
    if not isinstance(settings_path, str) or not settings_path.strip():
        return None
    if not Path(python_path).is_absolute() or not Path(settings_path).is_absolute():
        return None
    return python_path, settings_path


def _windows_creation_flags() -> int:
    if sys.platform != WINDOWS_PLATFORM:
        return 0
    return getattr(subprocess, CREATE_NO_WINDOW_ATTRIBUTE, 0)
