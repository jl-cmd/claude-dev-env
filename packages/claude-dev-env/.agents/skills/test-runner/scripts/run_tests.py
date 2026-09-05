#!/usr/bin/env python3
"""Run pytest or Playwright after deterministic local readiness checks.

::

    python run_tests.py -- python -m pytest tests/
    python run_tests.py -- npx playwright test tests/account.spec.ts

The selected child receives its arguments unchanged, inherits this process's
environment and output streams, and runs from the selected project directory.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import preflight_checks
from test_runner_constants.config.constants import (
    ALL_EXECUTABLE_SUFFIXES,
    ALL_URL_TRAILING_PUNCTUATION,
    ARGUMENT_ASSIGNMENT_SEPARATOR,
    BASE_URL_FLAG,
    COMMAND_SEPARATOR,
    DEFAULT_DJANGO_URL,
    DEFAULT_PLAYWRIGHT_URL,
    ERROR_CHILD_COMMAND_REQUIRED,
    ERROR_CHILD_LAUNCH_TEMPLATE,
    ERROR_COMMAND_SEPARATOR_REQUIRED,
    ERROR_PREFLIGHT_FAILURE_TEMPLATE,
    ERROR_PROJECT_NOT_DIRECTORY_TEMPLATE,
    ERROR_UNSUPPORTED_RUNNER,
    EXIT_CODE_FAILURE,
    EXIT_CODE_INVALID_ARGUMENTS,
    MANAGE_PY_FILENAME,
    MINIMUM_NPX_ARGUMENT_COUNT,
    MINIMUM_PLAYWRIGHT_ARGUMENT_COUNT,
    NPX_EXECUTABLE_NAME,
    PLAYWRIGHT_EXECUTABLE_NAME,
    PLAYWRIGHT_RUNNER_NAME,
    PLAYWRIGHT_TEST_COMMAND_INDEX,
    PLAYWRIGHT_TEST_SUBCOMMAND,
    PROJECT_FLAG,
    PWD_ENVIRONMENT_NAME,
    PYTEST_EXECUTABLE_PREFIX,
    PYTEST_RUNNER_NAME,
    PYTHON_EXECUTABLE_PREFIX,
    PYTHON_MODULE_FLAG,
    SERVER_URL_PATTERN,
)

build_frontend = preflight_checks.build_frontend
check_django_database = preflight_checks.check_django_database
check_runserver_port_conflicts = preflight_checks.check_runserver_port_conflicts
check_server_health = preflight_checks.check_server_health
check_test_db_flag = preflight_checks.check_test_db_flag


@dataclass(frozen=True)
class SelectedRunner:
    """The supported runner selected from the child argument vector."""

    name: str
    is_playwright: bool


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(add_help=True)
    parser.add_argument(PROJECT_FLAG, type=Path, default=None)
    return parser


def _split_command_arguments(
    all_arguments: Sequence[str],
) -> tuple[list[str], list[str]]:
    all_arguments_as_list = list(all_arguments)
    if COMMAND_SEPARATOR not in all_arguments_as_list:
        raise ValueError(ERROR_COMMAND_SEPARATOR_REQUIRED)
    separator_index = all_arguments_as_list.index(COMMAND_SEPARATOR)
    launcher_arguments = all_arguments_as_list[:separator_index]
    child_arguments = all_arguments_as_list[separator_index + 1 :]
    if not child_arguments:
        raise ValueError(ERROR_CHILD_COMMAND_REQUIRED)
    return launcher_arguments, child_arguments


def _resolve_project_root(maybe_project_path: Path | None) -> Path:
    selected_path = maybe_project_path or Path(
        os.environ.get(PWD_ENVIRONMENT_NAME, os.getcwd())
    )
    resolved_path = selected_path.expanduser().resolve()
    if not resolved_path.is_dir():
        raise ValueError(ERROR_PROJECT_NOT_DIRECTORY_TEMPLATE.format(resolved_path))
    return resolved_path


def _parse_command_arguments(
    all_arguments: Sequence[str],
) -> tuple[Path, list[str]]:
    launcher_arguments, child_arguments = _split_command_arguments(all_arguments)
    parsed_arguments = _build_argument_parser().parse_args(launcher_arguments)
    project_root = _resolve_project_root(parsed_arguments.project)
    return project_root, child_arguments


def _basename_without_suffix(executable_path: str) -> str:
    executable_name = Path(executable_path).name.casefold()
    for each_suffix in ALL_EXECUTABLE_SUFFIXES:
        if executable_name.endswith(each_suffix):
            return executable_name.removesuffix(each_suffix)
    return executable_name


def _is_python_module_runner(
    all_child_arguments: Sequence[str],
) -> bool:
    executable_name = _basename_without_suffix(all_child_arguments[0])
    if not executable_name.startswith(PYTHON_EXECUTABLE_PREFIX):
        return False
    for each_index, each_argument in enumerate(all_child_arguments[1:], start=1):
        if each_argument != PYTHON_MODULE_FLAG:
            continue
        return (
            each_index + 1 < len(all_child_arguments)
            and all_child_arguments[each_index + 1] == PYTEST_RUNNER_NAME
        )
    return False


def _is_pytest_executable(executable_path: str) -> bool:
    return _basename_without_suffix(executable_path).startswith(
        PYTEST_EXECUTABLE_PREFIX
    )


def _is_playwright_executable(
    all_child_arguments: Sequence[str],
) -> bool:
    executable_name = _basename_without_suffix(all_child_arguments[0])
    if executable_name == PLAYWRIGHT_EXECUTABLE_NAME:
        return (
            len(all_child_arguments) >= MINIMUM_PLAYWRIGHT_ARGUMENT_COUNT
            and all_child_arguments[1] == PLAYWRIGHT_TEST_SUBCOMMAND
        )
    return (
        executable_name == NPX_EXECUTABLE_NAME
        and len(all_child_arguments) >= MINIMUM_NPX_ARGUMENT_COUNT
        and all_child_arguments[1] == PLAYWRIGHT_EXECUTABLE_NAME
        and all_child_arguments[PLAYWRIGHT_TEST_COMMAND_INDEX]
        == PLAYWRIGHT_TEST_SUBCOMMAND
    )


def select_runner(all_child_arguments: Sequence[str]) -> SelectedRunner:
    """Select one supported runner from an explicit child argv.

    Args:
        all_child_arguments: Child executable and its arguments.

    Returns:
        The selected runner classification.

    Raises:
        ValueError: The child argv is empty or unsupported.
    """
    if not all_child_arguments:
        raise ValueError(ERROR_CHILD_COMMAND_REQUIRED)
    if _is_playwright_executable(all_child_arguments):
        return SelectedRunner(PLAYWRIGHT_RUNNER_NAME, True)
    if _is_pytest_executable(all_child_arguments[0]) or _is_python_module_runner(
        all_child_arguments
    ):
        return SelectedRunner(PYTEST_RUNNER_NAME, False)
    raise ValueError(ERROR_UNSUPPORTED_RUNNER)


def extract_target_url(
    all_child_arguments: Sequence[str],
    is_playwright: bool,
) -> str:
    """Return a URL carried by child args or the runner's local default.

    Args:
        all_child_arguments: Child executable and its arguments.
        is_playwright: Whether to use the Playwright default URL.

    Returns:
        An explicit base URL or the selected runner's default URL.
    """
    for each_index, each_argument in enumerate(all_child_arguments):
        if each_argument == BASE_URL_FLAG and each_index + 1 < len(all_child_arguments):
            return all_child_arguments[each_index + 1].rstrip(
                ALL_URL_TRAILING_PUNCTUATION
            )
        if each_argument.startswith(f"{BASE_URL_FLAG}{ARGUMENT_ASSIGNMENT_SEPARATOR}"):
            return each_argument.split(ARGUMENT_ASSIGNMENT_SEPARATOR, 1)[1].rstrip(
                ALL_URL_TRAILING_PUNCTUATION
            )
        url_match = SERVER_URL_PATTERN.search(each_argument)
        if url_match:
            return url_match.group(0).rstrip(ALL_URL_TRAILING_PUNCTUATION)
    return DEFAULT_PLAYWRIGHT_URL if is_playwright else DEFAULT_DJANGO_URL


def _run_django_preflight(project_root: Path, target_url: str) -> str | None:
    database_error = check_django_database(project_root)
    if database_error:
        return database_error
    return check_server_health(target_url)


def _run_playwright_preflight(
    project_root: Path,
    target_url: str,
) -> str | None:
    conflict_error = check_runserver_port_conflicts(target_url, project_root)
    if conflict_error:
        return conflict_error
    test_database_error = check_test_db_flag(target_url, project_root)
    if test_database_error:
        return test_database_error
    return build_frontend(project_root) or check_server_health(target_url)


def run_preflight(
    selected_runner: SelectedRunner,
    project_root: Path,
    all_child_arguments: Sequence[str],
) -> str | None:
    """Run checks required by the selected runner before child launch.

    Args:
        selected_runner: Runner selected from child argv.
        project_root: Directory used for project checks.
        all_child_arguments: Complete child argv used for URL selection.

    Returns:
        A blocking diagnostic when a readiness check fails, otherwise None.
    """
    is_django_project = (project_root / MANAGE_PY_FILENAME).is_file()
    if not selected_runner.is_playwright and not is_django_project:
        return None
    target_url = extract_target_url(all_child_arguments, selected_runner.is_playwright)
    if is_django_project and not selected_runner.is_playwright:
        return _run_django_preflight(project_root, target_url)
    if selected_runner.is_playwright:
        return _run_playwright_preflight(project_root, target_url)
    return check_server_health(target_url)


def run_child_process(
    all_child_arguments: Sequence[str],
    project_root: Path,
) -> int:
    """Run the child with inherited streams and environment.

    Args:
        all_child_arguments: Child executable and its arguments.
        project_root: Working directory for the child.

    Returns:
        The child's exit status, or one when the child cannot start.
    """
    try:
        completed_process = subprocess.run(
            list(all_child_arguments),
            cwd=project_root,
            check=False,
        )
    except OSError as error:
        print(ERROR_CHILD_LAUNCH_TEMPLATE.format(error), file=sys.stderr)
        return EXIT_CODE_FAILURE
    return completed_process.returncode


def main(all_arguments: Sequence[str]) -> int:
    """Validate and run one explicit test command.

    Args:
        all_arguments: Command arguments without the executable name.

    Returns:
        A validation or child exit status.
    """
    try:
        project_root, all_child_arguments = _parse_command_arguments(all_arguments)
        selected_runner = select_runner(all_child_arguments)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return EXIT_CODE_INVALID_ARGUMENTS
    try:
        preflight_error = run_preflight(
            selected_runner, project_root, all_child_arguments
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(ERROR_PREFLIGHT_FAILURE_TEMPLATE.format(error), file=sys.stderr)
        return EXIT_CODE_FAILURE
    if preflight_error:
        print(preflight_error, file=sys.stderr)
        return EXIT_CODE_FAILURE
    return run_child_process(all_child_arguments, project_root)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
