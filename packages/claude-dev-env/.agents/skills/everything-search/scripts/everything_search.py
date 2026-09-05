from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TextIO

from everything_search_command_constants.config.constants import (
    CLAUDE_DIRECTORY_NAME,
    EXECUTABLE_NAME,
    EXECUTION_ERROR_EXIT_CODE,
    INFORMATIONAL_ARGUMENT,
    INVALID_INPUT_EXIT_CODE,
    PROJECT_PATHS_FILE_NAME,
    REGISTRY_META_KEY,
    SEARCH_SCOPE_REQUIRED_MESSAGE,
    UTF8_ENCODING,
)


class RegistryRunFatal(ValueError):
    """Stop the run when the project-path registry is unreadable or invalid."""


def load_registry(registry_path: Path) -> dict[str, str]:
    """Read project names and absolute paths from a registry file.

    Args:
        registry_path: Registry file to read.

    Returns:
        The registered paths keyed by project name.

    Raises:
        RegistryRunFatal: The file is unreadable or its content is invalid.
    """
    if not registry_path.is_file():
        return {}
    try:
        all_registry_entries = json.loads(
            registry_path.read_text(encoding=UTF8_ENCODING)
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RegistryRunFatal(f"Malformed registry: {error}") from error
    return _validated_registry_entries(all_registry_entries)


def _validated_registry_entries(all_registry_entries: object) -> dict[str, str]:
    if not isinstance(all_registry_entries, dict):
        raise RegistryRunFatal("Invalid registry: expected an object")
    all_registered_paths_by_name: dict[str, str] = {}
    for each_registry_name, each_registered_path in all_registry_entries.items():
        if each_registry_name == REGISTRY_META_KEY:
            continue
        if not isinstance(each_registry_name, str) or not isinstance(
            each_registered_path, str
        ):
            raise RegistryRunFatal("Invalid registry: names and paths must be strings")
        if not _is_absolute_path(each_registered_path):
            raise RegistryRunFatal("Invalid registry: paths must be absolute")
        all_registered_paths_by_name[each_registry_name] = each_registered_path
    return all_registered_paths_by_name


def _is_absolute_path(search_argument: str) -> bool:
    try:
        return (
            PureWindowsPath(search_argument).is_absolute()
            or PurePosixPath(search_argument).is_absolute()
        )
    except ValueError:
        return False


def _registry_name(search_argument: str) -> str:
    if search_argument.startswith("{") and search_argument.endswith("}"):
        return search_argument[1:-1]
    return search_argument


def expand_search_arguments(
    all_search_arguments: Sequence[str],
    all_registered_paths_by_name: Mapping[str, str],
) -> list[str]:
    """Return the registered path for an exact project name or `{project-name}` token.

    Unknown names, absolute paths, flags, and spaces stay as their own arguments.

    Args:
        all_search_arguments: Everything search arguments.
        all_registered_paths_by_name: Absolute paths keyed by project name.

    Returns:
        Arguments with exact project names as their registered paths.
    """
    all_expanded_arguments: list[str] = []
    for each_search_argument in all_search_arguments:
        registry_name = _registry_name(each_search_argument)
        if (
            not _is_absolute_path(each_search_argument)
            and registry_name in all_registered_paths_by_name
        ):
            all_expanded_arguments.append(all_registered_paths_by_name[registry_name])
        else:
            all_expanded_arguments.append(each_search_argument)
    return all_expanded_arguments


def _run_search(
    executable_path: str,
    all_search_arguments: Sequence[str],
    search_stdout: TextIO,
    search_stderr: TextIO,
) -> int:
    try:
        search_run = subprocess.run(
            [executable_path, *all_search_arguments],
            capture_output=True,
            check=False,
            encoding=UTF8_ENCODING,
            shell=False,
            text=True,
        )
    except OSError as error:
        search_stderr.write(f"{error}\n")
        return EXECUTION_ERROR_EXIT_CODE
    search_stdout.write(search_run.stdout)
    search_stderr.write(search_run.stderr)
    return search_run.returncode


def _run_registered_search(
    all_search_arguments: Sequence[str],
    registry_path: Path,
    executable_path: str | None,
    search_stdout: TextIO,
    search_stderr: TextIO,
) -> int:
    try:
        all_registered_paths_by_name = load_registry(registry_path)
    except RegistryRunFatal as error:
        search_stderr.write(f"{error}\n")
        return INVALID_INPUT_EXIT_CODE
    selected_executable_path = executable_path or shutil.which(EXECUTABLE_NAME)
    if selected_executable_path is None:
        search_stderr.write(f"{EXECUTABLE_NAME} was not found.\n")
        return EXECUTION_ERROR_EXIT_CODE
    all_expanded_arguments = expand_search_arguments(
        all_search_arguments, all_registered_paths_by_name
    )
    return _run_search(
        selected_executable_path,
        all_expanded_arguments,
        search_stdout,
        search_stderr,
    )


def _has_search_scope(all_search_arguments: Sequence[str]) -> bool:
    first_argument = all_search_arguments[0]
    return bool(first_argument.strip()) and not first_argument.startswith("-")


def _is_informational_operation(all_search_arguments: Sequence[str]) -> bool:
    return (
        len(all_search_arguments) == 1
        and all_search_arguments[0].casefold() == INFORMATIONAL_ARGUMENT
    )


def main(all_search_arguments: Sequence[str]) -> int:
    """Expand project names and run one Everything search.

    Args:
        all_search_arguments: Arguments passed to Everything.

    Returns:
        The Everything process exit status or a command error status.
    """
    if not all_search_arguments:
        sys.stderr.write("At least one search argument is required.\n")
        return INVALID_INPUT_EXIT_CODE
    if not _has_search_scope(all_search_arguments) and not _is_informational_operation(
        all_search_arguments
    ):
        sys.stderr.write(SEARCH_SCOPE_REQUIRED_MESSAGE)
        return INVALID_INPUT_EXIT_CODE
    selected_registry_path = (
        Path.home() / CLAUDE_DIRECTORY_NAME / PROJECT_PATHS_FILE_NAME
    )
    return _run_registered_search(
        all_search_arguments,
        selected_registry_path,
        None,
        sys.stdout,
        sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
