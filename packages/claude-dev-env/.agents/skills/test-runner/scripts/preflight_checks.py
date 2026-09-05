"""Readiness checks for check_server_health, check_django_database,
check_test_db_flag, check_runserver_port_conflicts, and build_frontend."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

from test_runner_constants.config.constants import (
    ALL_BLOCKED_STATUS_CODES,
    ALL_COLLECTSTATIC_ARGUMENTS,
    ALL_FRONTEND_BUILD_ARGUMENTS,
    ALL_LOCAL_SERVER_HOSTS,
    ALL_PROCESS_INFORMATION_FIELDS,
    ALL_RUNSERVER_OPTIONS_WITH_VALUES,
    BUILD_TIMEOUT_SECONDS,
    COMMAND_ARGUMENT_SEPARATOR,
    CURL_EXECUTABLE_NAME,
    CURL_MAX_TIME_FLAG,
    CURL_OUTPUT_FLAG,
    CURL_SILENT_FLAG,
    CURL_STATUS_FORMAT,
    CURL_WRITE_OUT_FLAG,
    DEFAULT_DJANGO_PORT,
    DIRECTORY_LIST_SEPARATOR,
    DJANGO_DATABASE_FILENAME,
    EXIT_CODE_SUCCESS,
    FRONTEND_BUILD_FAILED_MESSAGE,
    FRONTEND_DIRECTORY_NAME,
    HEALTH_CHECK_ERROR_TEMPLATE,
    HEALTH_CHECK_TIMEOUT_SECONDS,
    MANAGE_PY_FILENAME,
    MINIMUM_PROCESS_ARGUMENT_COUNT,
    MINIMUM_RUNSERVER_PROCESS_COUNT,
    MISSING_DATABASE_ERROR_TEMPLATE,
    MISSING_TEST_DATABASE_FLAG_TEMPLATE,
    NULL_DEVICE_PATH,
    PORT_CONFLICT_ERROR_TEMPLATE,
    PROCESS_CURL_TIMEOUT_SECONDS,
    PROCESS_LIST_ARGUMENTS,
    PROCESS_LIST_RUNSERVER_TOKEN,
    PROCESS_LIST_SELF_FILTER_TOKEN,
    RUNSERVER_COMMAND_INDEX,
    RUNSERVER_COMMAND_NAME,
    TEST_DATABASE_FLAG,
    UNREACHABLE_ERROR_TEMPLATE,
)

try:
    import psutil
except ImportError:
    psutil = None


def check_server_health(target_url: str) -> str | None:
    """Return a diagnostic when the target server is unavailable.

    Args:
        target_url: HTTP endpoint to request.

    Returns:
        A diagnostic string when the endpoint cannot serve tests, otherwise None.
    """
    try:
        completed_process = subprocess.run(
            _build_curl_arguments(target_url),
            capture_output=True,
            text=True,
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
            check=False,
        )
        http_status_code = int(completed_process.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return UNREACHABLE_ERROR_TEMPLATE.format(target_url)
    return _server_health_error(target_url, http_status_code)


def _build_curl_arguments(target_url: str) -> list[str]:
    return [
        CURL_EXECUTABLE_NAME,
        CURL_SILENT_FLAG,
        CURL_OUTPUT_FLAG,
        NULL_DEVICE_PATH,
        CURL_WRITE_OUT_FLAG,
        CURL_STATUS_FORMAT,
        CURL_MAX_TIME_FLAG,
        str(PROCESS_CURL_TIMEOUT_SECONDS),
        target_url,
    ]


def _server_health_error(target_url: str, http_status_code: int) -> str | None:
    if http_status_code == EXIT_CODE_SUCCESS:
        return UNREACHABLE_ERROR_TEMPLATE.format(target_url)
    if http_status_code in ALL_BLOCKED_STATUS_CODES:
        return HEALTH_CHECK_ERROR_TEMPLATE.format(
            target_url, f"HTTP {http_status_code}"
        )
    return None


def check_django_database(project_root: Path) -> str | None:
    """Return a diagnostic when a Django database file is missing.

    Args:
        project_root: Django project directory to inspect.

    Returns:
        A diagnostic when manage.py exists without db.sqlite3, otherwise None.
    """
    manage_py_path = project_root / MANAGE_PY_FILENAME
    if not manage_py_path.is_file():
        return None
    database_path = project_root / DJANGO_DATABASE_FILENAME
    if database_path.is_file():
        return None
    return MISSING_DATABASE_ERROR_TEMPLATE.format(
        DJANGO_DATABASE_FILENAME, project_root
    )


def extract_port_from_url(target_url: str) -> str:
    """Return the URL port used by Django diagnostics.

    Args:
        target_url: URL whose authority may carry a port.

    Returns:
        The explicit port, or the Django default when no valid port exists.
    """
    try:
        parsed_url = urlparse(target_url)
        if parsed_url.port is not None:
            return str(parsed_url.port)
    except ValueError:
        return DEFAULT_DJANGO_PORT
    return DEFAULT_DJANGO_PORT


def check_test_db_flag(target_url: str, project_root: Path) -> str | None:
    """Return a diagnostic when a detected runserver lacks test DB.

    Args:
        target_url: URL that identifies the expected Django port.
        project_root: Django project that owns the selected test run.

    Returns:
        A diagnostic when runserver is found without --test-db, otherwise None.
    """
    if not (project_root / MANAGE_PY_FILENAME).is_file():
        return None
    if (process_listing := _read_process_listing()) is None:
        return None
    target_port = extract_port_from_url(target_url)
    is_runserver_found = False
    for each_line in process_listing.splitlines():
        if PROCESS_LIST_RUNSERVER_TOKEN not in each_line:
            continue
        if PROCESS_LIST_SELF_FILTER_TOKEN in each_line:
            continue
        runserver_arguments = _extract_runserver_arguments(each_line)
        if not _runserver_uses_target_port(runserver_arguments, target_port):
            continue
        is_runserver_found = True
        if TEST_DATABASE_FLAG in runserver_arguments:
            return None
    if not is_runserver_found:
        return None
    return MISSING_TEST_DATABASE_FLAG_TEMPLATE.format(target_port, target_port)


def _extract_runserver_arguments(process_line: str) -> tuple[str, ...]:
    all_process_tokens = tuple(process_line.split())
    try:
        runserver_index = all_process_tokens.index(RUNSERVER_COMMAND_NAME)
    except ValueError:
        return ()
    return all_process_tokens[runserver_index + 1 :]


def _runserver_uses_target_port(
    all_runserver_arguments: Sequence[str], target_port: str
) -> bool:
    endpoint_argument = _find_runserver_endpoint_argument(all_runserver_arguments)
    if endpoint_argument is None:
        return target_port == DEFAULT_DJANGO_PORT
    return endpoint_argument == target_port or endpoint_argument.endswith(
        f":{target_port}"
    )


def _find_runserver_endpoint_argument(
    all_runserver_arguments: Sequence[str],
) -> str | None:
    should_skip_next_argument = False
    for each_argument in all_runserver_arguments:
        if should_skip_next_argument:
            should_skip_next_argument = False
            continue
        if each_argument in ALL_RUNSERVER_OPTIONS_WITH_VALUES:
            should_skip_next_argument = True
            continue
        if not each_argument.startswith("-"):
            return each_argument
    return None


def _read_process_listing() -> str | None:
    try:
        completed_process = subprocess.run(
            list(PROCESS_LIST_ARGUMENTS),
            capture_output=True,
            text=True,
            timeout=PROCESS_CURL_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed_process.stdout or ""


def _get_runserver_processes_on_port(
    target_port: str,
) -> list[tuple[int, str]]:
    if psutil is None:
        return []
    all_runserver_processes: list[tuple[int, str]] = []
    port_token = f":{target_port}"
    for each_process in psutil.process_iter(ALL_PROCESS_INFORMATION_FIELDS):
        process_record = _read_runserver_process(each_process, port_token)
        if process_record is not None:
            all_runserver_processes.append(process_record)
    return all_runserver_processes


def _read_runserver_process(
    process: object,
    port_token: str,
) -> tuple[int, str] | None:
    try:
        process_information = getattr(process, "info", {})
        if not isinstance(process_information, dict):
            return None
        commandline_parts = process_information.get("cmdline") or []
        if len(commandline_parts) < MINIMUM_PROCESS_ARGUMENT_COUNT:
            return None
        if commandline_parts[1] != MANAGE_PY_FILENAME:
            return None
        if commandline_parts[RUNSERVER_COMMAND_INDEX] != RUNSERVER_COMMAND_NAME:
            return None
        if port_token not in COMMAND_ARGUMENT_SEPARATOR.join(commandline_parts):
            return None
        process_identifier = process_information.get("pid")
        if not isinstance(process_identifier, int):
            return None
        return (process_identifier, process_information.get("cwd") or "")
    except (
        KeyError,
        psutil.AccessDenied,
        psutil.NoSuchProcess,
        psutil.ZombieProcess,
    ):
        return None


def check_runserver_port_conflicts(
    target_url: str,
    project_root: Path,
) -> str | None:
    """Return a diagnostic for cross-worktree runserver conflicts.

    Args:
        target_url: URL whose host and port identify the server.
        project_root: Project directory running the test command.

    Returns:
        A diagnostic when separate worktrees share the port, otherwise None.
    """
    parsed_target_url = urlparse(target_url)
    if (parsed_target_url.hostname or "") not in ALL_LOCAL_SERVER_HOSTS:
        return None
    target_port = str(parsed_target_url.port or DEFAULT_DJANGO_PORT)
    all_processes = _get_runserver_processes_on_port(target_port)
    all_directories = _unique_process_directories(all_processes)
    if _has_no_process_conflict(all_processes, all_directories):
        return None
    return _build_conflict_message(target_port, project_root, all_directories)


def _unique_process_directories(
    all_processes: Sequence[tuple[int, str]],
) -> set[str]:
    return {
        str(Path(each_directory).resolve())
        for _, each_directory in all_processes
        if each_directory
    }


def _has_no_process_conflict(
    all_processes: Sequence[tuple[int, str]],
    all_directories: set[str],
) -> bool:
    return (
        len(all_processes) < MINIMUM_RUNSERVER_PROCESS_COUNT
        or len(all_directories) < MINIMUM_RUNSERVER_PROCESS_COUNT
    )


def _build_conflict_message(
    target_port: str,
    project_root: Path,
    all_directories: set[str],
) -> str:
    project_root_realpath = str(project_root.resolve())
    all_other_worktrees = sorted(
        each_directory
        for each_directory in all_directories
        if each_directory != project_root_realpath
    )
    all_conflicting_directories = all_other_worktrees or sorted(all_directories)
    return PORT_CONFLICT_ERROR_TEMPLATE.format(
        target_port, DIRECTORY_LIST_SEPARATOR.join(all_conflicting_directories)
    )


def build_frontend(project_root: Path) -> str | None:
    """Build the frontend and collect Django static files when present.

    Args:
        project_root: Project directory containing the optional frontend.

    Returns:
        A diagnostic when either preparation step fails, otherwise None.
    """
    frontend_path = project_root / FRONTEND_DIRECTORY_NAME
    if not frontend_path.is_dir():
        return None
    if _run_preparation(ALL_FRONTEND_BUILD_ARGUMENTS, frontend_path):
        return FRONTEND_BUILD_FAILED_MESSAGE
    if not (project_root / MANAGE_PY_FILENAME).is_file():
        return None
    if _run_preparation(ALL_COLLECTSTATIC_ARGUMENTS, project_root):
        return FRONTEND_BUILD_FAILED_MESSAGE
    return None


def _run_preparation(
    all_arguments: Sequence[str],
    working_directory: Path,
) -> bool:
    try:
        completed_process = subprocess.run(
            list(all_arguments),
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=BUILD_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True
    return completed_process.returncode != EXIT_CODE_SUCCESS
