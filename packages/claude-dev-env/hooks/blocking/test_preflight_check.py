#!/usr/bin/env python3
"""
PreToolUse:Bash hook that validates prerequisites before running test commands.

Intercepts playwright/pytest commands and checks:
  1. Target server is reachable and healthy
  2. Database file exists (for Django projects)
  3. (Playwright only) Django server has --test-db flag
  4. (Playwright only) Frontend builds successfully before e2e tests

Blocks doomed test runs early instead of letting them hang for minutes.
"""
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse

try:
    import psutil
except Exception:
    psutil = None

TEST_COMMAND_PATTERNS = [
    re.compile(r'\bplaywright\s+test\b'),
    re.compile(r'\bnpx\s+playwright\b'),
    re.compile(r'\bpytest\b'),
    re.compile(r'\bpython\s+-m\s+pytest\b'),
]

SERVER_URL_PATTERN = re.compile(r'https?://[^\s"\']+')

DEFAULT_PLAYWRIGHT_URL = "http://localhost:3000"
DEFAULT_DJANGO_URL = "http://localhost:8000"

CURL_TIMEOUT_SECONDS = 2
DJANGO_DB_FILENAME = "db.sqlite3"

BLOCKED_STATUS_CODES = {500, 502, 503, 504}
HEALTH_CHECK_ERROR_TEMPLATE = "BLOCKED: Server at {} is not healthy ({}). Fix the server before running tests."
UNREACHABLE_ERROR_TEMPLATE = "BLOCKED: Server at {} is unreachable. Start the server before running tests."
MISSING_DB_ERROR_TEMPLATE = "BLOCKED: No database file ({}) found in {}. Run migrations before running tests."
FRONTEND_BUILD_FAILED_MESSAGE = "BLOCKED: Frontend build failed. Fix build errors before running e2e tests."
MISSING_TEST_DB_FLAG_TEMPLATE = "BLOCKED: Django server on port {} is not running with --test-db. Restart with: python manage.py runserver --test-db 0.0.0.0:{}"
PORT_CONFLICT_ERROR_TEMPLATE = "BLOCKED: Multiple Django runserver processes are bound to port {} across worktrees: {}. Stop stale servers first."
FRONTEND_DIRECTORY_NAME = "frontend"
NPM_BUILD_COMMAND = "npm run build"
COLLECTSTATIC_COMMAND = "python manage.py collectstatic --noinput"
BUILD_TIMEOUT_SECONDS = 120
PLAYWRIGHT_COMMAND_PATTERNS = [
    re.compile(r'\bplaywright\s+test\b'),
    re.compile(r'\bnpx\s+playwright\b'),
]


def is_test_command(command: str) -> bool:
    for each_pattern in TEST_COMMAND_PATTERNS:
        if each_pattern.search(command):
            return True
    return False


def is_playwright_command(command: str) -> bool:
    for each_pattern in PLAYWRIGHT_COMMAND_PATTERNS:
        if each_pattern.search(command):
            return True
    return False


def extract_target_url(command: str) -> str:
    url_match = SERVER_URL_PATTERN.search(command)
    if url_match:
        return url_match.group(0)

    is_playwright = "playwright" in command
    if is_playwright:
        return DEFAULT_PLAYWRIGHT_URL

    is_pytest = "pytest" in command
    if is_pytest:
        return DEFAULT_DJANGO_URL

    return DEFAULT_PLAYWRIGHT_URL


def check_server_health(target_url: str) -> str | None:
    try:
        curl_result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(CURL_TIMEOUT_SECONDS), target_url],
            capture_output=True,
            text=True,
            timeout=CURL_TIMEOUT_SECONDS + 1,
        )
        http_status_code = int(curl_result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return UNREACHABLE_ERROR_TEMPLATE.format(target_url)

    if http_status_code == 0:
        return UNREACHABLE_ERROR_TEMPLATE.format(target_url)

    if http_status_code in BLOCKED_STATUS_CODES:
        return HEALTH_CHECK_ERROR_TEMPLATE.format(target_url, f"HTTP {http_status_code}")

    return None


def find_project_root(command: str) -> str | None:
    working_directory = os.environ.get("PWD", os.getcwd())

    directory_match = re.search(r'--project[= ](\S+)', command)
    if directory_match:
        return os.path.abspath(directory_match.group(1))

    cd_match = re.search(r'cd\s+"([^"]+)"', command) or re.search(r"cd\s+'([^']+)'", command) or re.search(r'cd\s+(\S+)', command)
    if cd_match:
        cd_target = cd_match.group(1)
        if os.path.isabs(cd_target):
            return cd_target
        return os.path.join(working_directory, cd_target)

    return working_directory


def check_django_database(command: str) -> str | None:
    is_django_test = "pytest" in command or "manage.py" in command
    if not is_django_test:
        return None

    project_root = find_project_root(command)
    if not project_root:
        return None

    manage_py_path = os.path.join(project_root, "manage.py")
    if not os.path.exists(manage_py_path):
        return None

    database_path = os.path.join(project_root, DJANGO_DB_FILENAME)
    if os.path.exists(database_path):
        return None

    return MISSING_DB_ERROR_TEMPLATE.format(DJANGO_DB_FILENAME, project_root)


def find_frontend_directory(command: str) -> str | None:
    project_root = find_project_root(command)
    if not project_root:
        return None

    frontend_path = os.path.join(project_root, FRONTEND_DIRECTORY_NAME)
    if os.path.isdir(frontend_path):
        return frontend_path

    return None


def build_frontend(command: str) -> str | None:
    frontend_path = find_frontend_directory(command)
    if not frontend_path:
        return None

    project_root = find_project_root(command)

    npm_build_result = subprocess.run(
        NPM_BUILD_COMMAND.split(),
        cwd=frontend_path,
        capture_output=True,
        text=True,
        timeout=BUILD_TIMEOUT_SECONDS,
    )
    if npm_build_result.returncode != 0:
        return FRONTEND_BUILD_FAILED_MESSAGE

    collectstatic_result = subprocess.run(
        COLLECTSTATIC_COMMAND.split(),
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=BUILD_TIMEOUT_SECONDS,
    )
    if collectstatic_result.returncode != 0:
        return FRONTEND_BUILD_FAILED_MESSAGE

    return None


def extract_port_from_url(target_url: str) -> str:
    parsed_url = urlparse(target_url)
    if parsed_url.port:
        return str(parsed_url.port)
    return "8000"


def check_test_db_flag(target_url: str) -> str | None:
    port = extract_port_from_url(target_url)

    try:
        ps_result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=CURL_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    is_runserver_found = False
    for each_line in ps_result.stdout.splitlines():
        if "runserver" not in each_line:
            continue
        if "grep" in each_line:
            continue
        is_runserver_found = True
        if "--test-db" in each_line:
            return None

    if not is_runserver_found:
        return None

    return MISSING_TEST_DB_FLAG_TEMPLATE.format(port, port)


def _get_runserver_processes_on_port(target_port: str) -> list[tuple[int, str]]:
    if psutil is None:
        return []

    runserver_processes: list[tuple[int, str]] = []
    port_token = f":{target_port}"

    for each_process in psutil.process_iter(["pid", "cmdline", "cwd"]):
        try:
            commandline_parts = each_process.info.get("cmdline") or []
            if len(commandline_parts) < 3:
                continue
            if commandline_parts[1] != "manage.py" or commandline_parts[2] != "runserver":
                continue

            full_commandline = " ".join(commandline_parts)
            if port_token not in full_commandline:
                continue

            process_working_directory = each_process.info.get("cwd") or ""
            runserver_processes.append((each_process.info["pid"], process_working_directory))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, KeyError):
            continue

    return runserver_processes


def check_runserver_port_conflicts(target_url: str, project_root: str | None) -> str | None:
    parsed_target_url = urlparse(target_url)
    target_host = parsed_target_url.hostname or ""
    if target_host not in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return None

    target_port = str(parsed_target_url.port or 8000)
    runserver_processes = _get_runserver_processes_on_port(target_port)
    if len(runserver_processes) <= 1:
        return None

    project_root_realpath = os.path.realpath(project_root) if project_root else None
    unique_directories: set[str] = set()
    for _, directory_path in runserver_processes:
        if not directory_path:
            continue
        unique_directories.add(os.path.realpath(directory_path))

    if len(unique_directories) <= 1:
        return None

    if project_root_realpath and project_root_realpath in unique_directories:
        other_worktrees = sorted(path for path in unique_directories if path != project_root_realpath)
        if not other_worktrees:
            return None
        return PORT_CONFLICT_ERROR_TEMPLATE.format(target_port, ", ".join(other_worktrees))

    return PORT_CONFLICT_ERROR_TEMPLATE.format(target_port, ", ".join(sorted(unique_directories)))


def build_deny_response(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    if not is_test_command(command):
        sys.exit(0)

    project_root = find_project_root(command)
    is_django_project = project_root and os.path.exists(os.path.join(project_root, "manage.py"))

    if not is_django_project and not is_playwright_command(command):
        sys.exit(0)

    database_error = check_django_database(command)
    if database_error:
        print(json.dumps(build_deny_response(database_error)))
        sys.exit(0)

    target_url = extract_target_url(command)

    is_e2e_test = is_playwright_command(command)
    if is_e2e_test:
        conflict_error = check_runserver_port_conflicts(target_url, project_root)
        if conflict_error:
            print(json.dumps(build_deny_response(conflict_error)))
            sys.exit(0)

        test_db_error = check_test_db_flag(target_url)
        if test_db_error:
            print(json.dumps(build_deny_response(test_db_error)))
            sys.exit(0)

        frontend_build_error = build_frontend(command)
        if frontend_build_error:
            print(json.dumps(build_deny_response(frontend_build_error)))
            sys.exit(0)

    server_error = check_server_health(target_url)
    if server_error:
        print(json.dumps(build_deny_response(server_error)))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
