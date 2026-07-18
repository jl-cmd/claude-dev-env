#!/usr/bin/env python3
"""Launch the hookless ``claude -p --bare`` sandbox session in a worktree.

::

    python launch_sandbox.py --worktree ./wt --settings ./s.json --task-file ./t.txt
    {"worktree": "./wt", "settings": "./s.json", "exit_code": 0}

The launcher validates the three paths, reads the proof-of-concept task from
the task file, and runs a headless ``claude`` session in the worktree under
the minimal safety settings. The session runs with the standards gates
stripped, so the two safety hooks in the settings are its only containment.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from prototype_scripts_constants.launch_sandbox_constants import (
    BARE_FLAG,
    CLAUDE_EXECUTABLE_NAME,
    DEFAULT_TIMEOUT_SECONDS,
    LAUNCH_MISSING_PATH_EXIT_CODE,
    PROMPT_FLAG,
    SETTINGS_FLAG,
    SKIP_PERMISSIONS_FLAG,
    SUMMARY_KEY_EXIT_CODE,
    SUMMARY_KEY_SETTINGS,
    SUMMARY_KEY_WORKTREE,
)
from prototype_scripts_constants.prototype_common_constants import (
    LOGGING_FORMAT,
    TEXT_ENCODING_UTF8,
)

logger = logging.getLogger("launch_sandbox")

SandboxCommandRunner = Callable[[list[str], Path, "int | None"], int]


def build_sandbox_command(task_text: str, settings_path: Path) -> list[str]:
    """Build the exact headless ``claude`` argument vector for the sandbox.

    ::

        "build a spike", settings.json
            -> ["claude", "-p", "build a spike", "--bare",
                "--dangerously-skip-permissions", "--settings", "settings.json"]

    Args:
        task_text: the proof-of-concept task the session builds.
        settings_path: the minimal safety settings file.

    Returns:
        The ordered argument vector for the headless claude session.
    """
    return [
        CLAUDE_EXECUTABLE_NAME,
        PROMPT_FLAG,
        task_text,
        BARE_FLAG,
        SKIP_PERMISSIONS_FLAG,
        SETTINGS_FLAG,
        str(settings_path),
    ]


def validate_sandbox_paths(
    worktree_path: Path, settings_path: Path, task_file_path: Path
) -> str | None:
    """Report the first path that does not fit the sandbox launch contract.

    Args:
        worktree_path: the isolated worktree the session runs in.
        settings_path: the minimal safety settings file.
        task_file_path: the file holding the proof-of-concept task text.

    Returns:
        An error message for the first path that is absent or the wrong
        kind, or None when the worktree is a directory and both files exist.
    """
    if not worktree_path.is_dir():
        return f"worktree is not a directory: {worktree_path}"
    if not settings_path.is_file():
        return f"settings file not found: {settings_path}"
    if not task_file_path.is_file():
        return f"task file not found: {task_file_path}"
    return None


def _run_via_subprocess(
    all_command_tokens: list[str], working_directory: Path, timeout_seconds: int | None
) -> int:
    completed_process = subprocess.run(
        all_command_tokens,
        cwd=working_directory,
        timeout=timeout_seconds,
        check=False,
    )
    return completed_process.returncode


def run_sandbox(
    worktree_path: Path,
    settings_path: Path,
    task_text: str,
    timeout_seconds: int | None,
    command_runner: SandboxCommandRunner,
) -> int:
    """Run the headless sandbox command in the worktree and return its code.

    Args:
        worktree_path: the isolated worktree the session runs in.
        settings_path: the minimal safety settings file.
        task_text: the proof-of-concept task the session builds.
        timeout_seconds: the wall-clock limit, or None for no limit.
        command_runner: the callable that runs the command vector.

    Returns:
        The exit code the command runner reports for the session.
    """
    sandbox_command = build_sandbox_command(task_text, settings_path)
    return command_runner(sandbox_command, worktree_path, timeout_seconds)


def _emit_sandbox_summary(
    worktree_path: Path, settings_path: Path, exit_code: int
) -> None:
    summary = {
        SUMMARY_KEY_WORKTREE: str(worktree_path),
        SUMMARY_KEY_SETTINGS: str(settings_path),
        SUMMARY_KEY_EXIT_CODE: exit_code,
    }
    sys.stdout.write(json.dumps(summary) + "\n")


def _parse_arguments(all_arguments: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", required=True, help="the sandbox worktree")
    parser.add_argument("--settings", required=True, help="the safety settings file")
    parser.add_argument("--task-file", required=True, help="the task text file")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="the wall-clock limit for the session",
    )
    return parser.parse_args(all_arguments)


def main(all_arguments: list[str] | None = None) -> int:
    """Validate the paths, then run the sandbox session and print a summary.

    Args:
        all_arguments: the command-line arguments, or None to read sys.argv.

    Returns:
        The sandbox exit code, or 2 when a required path is missing.
    """
    logging.basicConfig(format=LOGGING_FORMAT)
    arguments = _parse_arguments(all_arguments)
    worktree_path = Path(arguments.worktree).expanduser()
    settings_path = Path(arguments.settings).expanduser()
    task_file_path = Path(arguments.task_file).expanduser()
    path_error = validate_sandbox_paths(worktree_path, settings_path, task_file_path)
    if path_error is not None:
        logger.error("%s", path_error)
        return LAUNCH_MISSING_PATH_EXIT_CODE
    task_text = task_file_path.read_text(encoding=TEXT_ENCODING_UTF8)
    exit_code = run_sandbox(
        worktree_path,
        settings_path,
        task_text,
        arguments.timeout_seconds,
        _run_via_subprocess,
    )
    _emit_sandbox_summary(worktree_path, settings_path, exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
