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


def discover_mypy_config(target_file: Path) -> Path | None:
    """Return the nearest ancestor ``pyproject.toml`` that configures mypy.

    Mypy applies a project's ``[tool.mypy]`` settings only when the config file
    is on its invocation path; handing the discovered config to mypy lets a
    check run from the repository root still honor the project's own import
    resolution settings (such as ``ignore_missing_imports``) for a module that
    imports its siblings by name. Reuses the validators-package walk-up so the
    discovery logic lives in one place.

    Args:
        target_file: The Python file mypy will check.

    Returns:
        The nearest ancestor ``pyproject.toml`` declaring a ``[tool.mypy]``
        table, or None when none exists above the file or the walk-up helper
        cannot be imported.
    """
    validators_directory = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validators"
    )
    if validators_directory not in sys.path:
        sys.path.insert(0, validators_directory)
    try:
        integration_module = importlib.import_module("mypy_integration")
    except ImportError:
        return None
    discovered_config = integration_module.find_pyproject_with_mypy_config(target_file)
    return discovered_config if isinstance(discovered_config, Path) else None


def build_mypy_command(relative_file_path: str, mypy_config_file: Path | None) -> list[str]:
    """Build the mypy command line for one file.

    Args:
        relative_file_path: The target file path relative to the project root.
        mypy_config_file: The ``pyproject.toml`` to pass via ``--config-file``,
            or None to let mypy fall back to its own config discovery.

    Returns:
        The full mypy argument vector, including the interpreter prefix on
        Windows and the config file when one was discovered.
    """
    base_command = [sys.executable, "-m", "mypy"] if IS_WINDOWS else ["mypy"]

    config_arguments = (
        ["--config-file", str(mypy_config_file)] if mypy_config_file is not None else []
    )
    return base_command + config_arguments + [
        "--no-error-summary",
        "--show-error-codes",
        "--no-color",
        relative_file_path,
    ]


def run_mypy(target_file: str, project_root: str) -> tuple[int, str]:
    """Run mypy on one file from the project root and return its result.

    Args:
        target_file: The absolute path of the file to type-check.
        project_root: The directory mypy runs from.

    Returns:
        The mypy exit code paired with its combined stdout and stderr text.
    """
    relative_file_path = os.path.relpath(target_file, project_root)
    mypy_config_file = discover_mypy_config(Path(target_file))
    mypy_command = build_mypy_command(relative_file_path, mypy_config_file)

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
