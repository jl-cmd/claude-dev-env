"""Names, messages, and limits used by the explicit test runner."""

from __future__ import annotations

import re

DEFAULT_DJANGO_URL: str = "http://localhost:8000"
DEFAULT_PLAYWRIGHT_URL: str = "http://localhost:3000"
DJANGO_DATABASE_FILENAME: str = "db.sqlite3"
MANAGE_PY_FILENAME: str = "manage.py"
FRONTEND_DIRECTORY_NAME: str = "frontend"
PYTEST_RUNNER_NAME: str = "pytest"
PLAYWRIGHT_RUNNER_NAME: str = "playwright"
PYTHON_MODULE_FLAG: str = "-m"
PLAYWRIGHT_TEST_SUBCOMMAND: str = "test"
COMMAND_SEPARATOR: str = "--"
PROJECT_FLAG: str = "--project"
BASE_URL_FLAG: str = "--base-url"
ALL_EXECUTABLE_SUFFIXES: tuple[str, ...] = (".exe", ".cmd", ".bat")
ARGUMENT_ASSIGNMENT_SEPARATOR: str = "="
COMMAND_ARGUMENT_SEPARATOR: str = " "
DIRECTORY_LIST_SEPARATOR: str = ", "
PWD_ENVIRONMENT_NAME: str = "PWD"
PYTHON_EXECUTABLE_PREFIX: str = "python"
PYTEST_EXECUTABLE_PREFIX: str = "pytest"
PLAYWRIGHT_EXECUTABLE_NAME: str = "playwright"
NPX_EXECUTABLE_NAME: str = "npx"
RUNSERVER_COMMAND_NAME: str = "runserver"
TEST_DATABASE_FLAG: str = "--test-db"
ALL_RUNSERVER_OPTIONS_WITH_VALUES: frozenset[str] = frozenset(
    {"--pythonpath", "--settings", "--verbosity"}
)
PROCESS_LIST_ARGUMENTS: tuple[str, ...] = ("ps", "aux")
ALL_PROCESS_INFORMATION_FIELDS: tuple[str, ...] = ("pid", "cmdline", "cwd")
ALL_FRONTEND_BUILD_ARGUMENTS: tuple[str, ...] = ("npm", "run", "build")
ALL_COLLECTSTATIC_ARGUMENTS: tuple[str, ...] = (
    "python",
    "manage.py",
    "collectstatic",
    "--noinput",
)
CURL_EXECUTABLE_NAME: str = "curl"
CURL_SILENT_FLAG: str = "-s"
CURL_OUTPUT_FLAG: str = "-o"
CURL_WRITE_OUT_FLAG: str = "-w"
CURL_STATUS_FORMAT: str = "%{http_code}"
CURL_MAX_TIME_FLAG: str = "--max-time"
NULL_DEVICE_PATH: str = "/dev/null"
ALL_LOCAL_SERVER_HOSTS: frozenset[str] = frozenset(
    {"localhost", "127.0.0.1", "0.0.0.0"}
)
ALL_BLOCKED_STATUS_CODES: frozenset[int] = frozenset({500, 502, 503, 504})
SERVER_URL_PATTERN: re.Pattern[str] = re.compile(r"https?://[^\s\"']+")
ALL_URL_TRAILING_PUNCTUATION: str = ".,;:)]}"
DEFAULT_DJANGO_PORT: str = "8000"
PROCESS_CURL_TIMEOUT_SECONDS: int = 2
HEALTH_CHECK_TIMEOUT_SECONDS: int = 3
BUILD_TIMEOUT_SECONDS: int = 120
EXIT_CODE_SUCCESS: int = 0
EXIT_CODE_FAILURE: int = 1
EXIT_CODE_INVALID_ARGUMENTS: int = 2
MINIMUM_PLAYWRIGHT_ARGUMENT_COUNT: int = 2
MINIMUM_NPX_ARGUMENT_COUNT: int = 3
MINIMUM_PROCESS_ARGUMENT_COUNT: int = 3
MINIMUM_RUNSERVER_PROCESS_COUNT: int = 2
RUNSERVER_COMMAND_INDEX: int = 2
PLAYWRIGHT_TEST_COMMAND_INDEX: int = 2
ERROR_COMMAND_SEPARATOR_REQUIRED: str = "the child command must follow --"
ERROR_CHILD_COMMAND_REQUIRED: str = "a supported child test command is required"
ERROR_UNSUPPORTED_RUNNER: str = "only pytest and playwright test commands are supported"
ERROR_PREFLIGHT_FAILURE_TEMPLATE: str = "test preflight failed: {}"
ERROR_PROJECT_NOT_DIRECTORY_TEMPLATE: str = "project is not a directory: {}"
ERROR_CHILD_LAUNCH_TEMPLATE: str = "test child could not start: {}"
HEALTH_CHECK_ERROR_TEMPLATE: str = (
    "BLOCKED: Server at {} is not healthy ({}). Fix the server before running tests."
)
UNREACHABLE_ERROR_TEMPLATE: str = (
    "BLOCKED: Server at {} is unreachable. Start the server before running tests."
)
MISSING_DATABASE_ERROR_TEMPLATE: str = (
    "BLOCKED: No database file ({}) found in {}. Run migrations before running tests."
)
FRONTEND_BUILD_FAILED_MESSAGE: str = (
    "BLOCKED: Frontend build failed. Fix build errors before running e2e tests."
)
MISSING_TEST_DATABASE_FLAG_TEMPLATE: str = (
    "BLOCKED: Django server on port {} is not running with --test-db. Restart "
    "with: python manage.py runserver --test-db 0.0.0.0:{}"
)
PORT_CONFLICT_ERROR_TEMPLATE: str = (
    "BLOCKED: Multiple Django runserver processes are bound to port {} across "
    "worktrees: {}. Stop stale servers first."
)
PROCESS_LIST_RUNSERVER_TOKEN: str = "runserver"
PROCESS_LIST_SELF_FILTER_TOKEN: str = "grep"
UTF8_ENCODING: str = "utf-8"
