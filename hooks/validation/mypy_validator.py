#!/usr/bin/env python3
"""
Mypy validation hook - blocks Write/Edit if mypy finds type errors.

This catches:
- Missing attributes (e.g., HumanActions has no attribute 'press_key')
- Wrong function signatures
- Type mismatches
- Import errors

Works in both WSL and Windows for any Python project with a git root.
Project root is discovered via CLAUDE_PROJECT_ROOT env var or git rev-parse.
"""
import importlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from types import ModuleType

NOTIFICATION_UTILS_DIRECTORY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notification"
)
sys.path.insert(0, NOTIFICATION_UTILS_DIRECTORY)


def load_notification_utils() -> ModuleType | None:
    try:
        return importlib.import_module("notification_utils")
    except ImportError:
        return None


IS_WINDOWS = platform.system() == "Windows"

GIT_COMMAND_TIMEOUT_SECONDS = 5
MYPY_TIMEOUT_SECONDS = 60
MAXIMUM_DISPLAYED_ERRORS = 5

SKIP_PATTERNS = {"test_", "_test.", "conftest", "/tests/", "\\tests\\", "fixture", "mock"}


def discover_project_root(target_file: str) -> Path | None:
    if env_root := os.environ.get("CLAUDE_PROJECT_ROOT"):
        return Path(env_root)

    try:
        completed_process = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=str(Path(target_file).parent),
        )
        if completed_process.returncode != 0:
            return None
        return Path(completed_process.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def is_file_within_project(target_file: str, project_root: Path) -> bool:
    try:
        Path(target_file).resolve().relative_to(project_root.resolve())
        return True
    except ValueError:
        return False


def build_mypy_command(relative_file_path: str) -> list[str]:
    if IS_WINDOWS:
        base_command = [sys.executable, "-m", "mypy"]
    else:
        base_command = ["mypy"]

    return base_command + [
        "--no-error-summary",
        "--show-error-codes",
        "--no-color",
        relative_file_path,
    ]


def run_mypy(target_file: str, project_root: str) -> tuple[int, str]:
    relative_file_path = os.path.relpath(target_file, project_root)
    mypy_command = build_mypy_command(relative_file_path)

    completed_process = subprocess.run(
        mypy_command,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=MYPY_TIMEOUT_SECONDS,
        cwd=project_root,
    )

    stdout_output = completed_process.stdout.strip()
    stderr_output = completed_process.stderr.strip()
    combined_output = f"{stdout_output}\n{stderr_output}".strip() if stderr_output else stdout_output

    return completed_process.returncode, combined_output


def extract_error_lines(mypy_output: str) -> list[str]:
    all_lines = mypy_output.strip().split("\n")
    return [each_line for each_line in all_lines if ": error:" in each_line]


def format_error_summary(all_error_lines: list[str]) -> str:
    displayed_errors = all_error_lines[:MAXIMUM_DISPLAYED_ERRORS]
    error_summary = "\n".join(f"  {each_line}" for each_line in displayed_errors)

    remaining_error_count = len(all_error_lines) - MAXIMUM_DISPLAYED_ERRORS
    if remaining_error_count > 0:
        error_summary += f"\n  ... and {remaining_error_count} more"

    return error_summary


def send_block_notification(error_summary: str) -> None:
    notification_module = load_notification_utils()
    if notification_module is None:
        return

    notification_title = "Mypy Type Errors"
    notification_body = f"Write blocked: {error_summary[:200]}"

    try:
        if notification_module.is_wsl():
            notification_module.notify_wsl(notification_title, notification_body)
        elif platform.system() == "Linux":
            notification_module.notify_linux()
        elif platform.system() == "Windows":
            notification_module.notify_windows(notification_title, notification_body)
    except (AttributeError, OSError):
        pass


def build_block_response(error_summary: str) -> dict[str, str | dict[str, str]]:
    return {
        "decision": "block",
        "reason": f"[MYPY] Type errors: {error_summary}",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
        },
    }


def parse_file_path_from_stdin() -> str:
    try:
        hook_event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return ""

    return hook_event.get("tool_input", {}).get("file_path", "")


def is_test_file(python_file: Path) -> bool:
    name_lower = python_file.name.lower()
    path_lower = str(python_file).lower()

    return any(
        each_pattern in name_lower or each_pattern in path_lower
        for each_pattern in SKIP_PATTERNS
    )


def main() -> None:
    target_file_path = parse_file_path_from_stdin()

    if not target_file_path:
        sys.exit(0)

    target_file = Path(target_file_path)

    if target_file.suffix.lower() != ".py":
        sys.exit(0)

    if is_test_file(target_file):
        sys.exit(0)

    if not target_file.exists():
        sys.exit(0)

    project_root = discover_project_root(target_file_path)
    if project_root is None:
        sys.exit(0)

    if not is_file_within_project(target_file_path, project_root):
        sys.exit(0)

    try:
        mypy_exit_code, mypy_output = run_mypy(target_file_path, str(project_root))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        sys.exit(0)

    if mypy_exit_code == 0:
        sys.exit(0)

    all_error_lines = extract_error_lines(mypy_output)

    if not all_error_lines:
        sys.exit(0)

    error_summary = format_error_summary(all_error_lines)
    send_block_notification(error_summary)
    block_response = build_block_response(error_summary)
    print(json.dumps(block_response))
    sys.exit(0)


if __name__ == "__main__":
    main()
