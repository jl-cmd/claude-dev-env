#!/usr/bin/env python3

"""Format eligible newly written source files without blocking the write."""

from __future__ import annotations

import importlib
import json
import os
import platform
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

NOTIFICATION_UTILS_DIRECTORY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notification"
)
sys.path.insert(0, NOTIFICATION_UTILS_DIRECTORY)

PYTHON_EXTENSIONS = frozenset({".py"})
JS_EXTENSIONS = frozenset({".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"})
JSON_EXTENSIONS = frozenset({".json"})
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOKS_DIR = os.path.join(PLUGIN_ROOT, "hooks") + os.sep
PYTHON_FORMAT_TIMEOUT_SECONDS = 12
JS_FORMAT_TIMEOUT_SECONDS = 30
GIT_LS_FILES_TIMEOUT_SECONDS = 5
WRITE_TOOL_NAME = "Write"
PYTHON_FORMATTER_NAME = "python"
PRETTIER_FORMATTER_NAME = "prettier"
NPX_EXECUTABLE = "npx.cmd" if os.name == "nt" else "npx"
FORMATTER_DIAGNOSTIC_TEMPLATE = "auto-formatter: %s: %s\n"
FORMATTER_DIAGNOSTIC_SEPARATOR = "\n"
FORMATTER_TIMEOUT_DIAGNOSTIC_TEMPLATE = "auto-formatter: %s timed out after %d seconds\n"
PRETTIER_CONFIG_NAMES = frozenset(
    {
        ".prettierrc",
        ".prettierrc.json",
        ".prettierrc.yml",
        ".prettierrc.yaml",
        ".prettierrc.js",
        ".prettierrc.cjs",
        ".prettierrc.mjs",
        ".prettierrc.toml",
        "prettier.config.js",
        "prettier.config.cjs",
        "prettier.config.mjs",
    }
)


def load_notification_utils() -> ModuleType | None:
    try:
        return importlib.import_module("notification_utils")
    except ImportError:
        return None


def send_format_notification(file_path: str, formatter_name: str) -> None:
    notification_module = load_notification_utils()
    if notification_module is None:
        return

    notification_title = "Auto-Formatter"
    notification_body = f"{formatter_name} formatted: {Path(file_path).name}"

    try:
        if notification_module.is_wsl():
            notification_module.notify_wsl(notification_title, notification_body)
        elif platform.system() == "Linux":
            notification_module.notify_linux()
        elif platform.system() == "Windows":
            notification_module.notify_windows(notification_title, notification_body)
    except (AttributeError, OSError):
        pass


def has_prettier_config(file_path: str) -> bool:
    each_ancestor = Path(file_path).resolve().parent
    while True:
        if any(
            (each_ancestor / each_config_name).exists()
            for each_config_name in PRETTIER_CONFIG_NAMES
        ):
            return True
        parent_directory = each_ancestor.parent
        if parent_directory == each_ancestor:
            return False
        each_ancestor = parent_directory


def budgeted_python_format_seconds() -> int:
    """Return the wall-clock budget for the two-subprocess happy path.

    The fix loop breaks on the first command that runs — whether it returns zero
    or non-zero — or on a timeout, and continues to the next command only when a
    command is missing (FileNotFoundError). The format loop breaks only on a
    returncode of zero or on a timeout, and continues on a non-zero return or a
    missing command. The common case spends one fix subprocess plus one format
    subprocess. This is a budget for that assumed path, not a guaranteed upper
    bound: when commands are missing or time out the loops can spend more than
    this budget.
    """
    return PYTHON_FORMAT_TIMEOUT_SECONDS * 2


def is_untracked_in_git(file_path: str) -> bool:
    """Check if file is untracked (brand new) by git."""
    containing_directory = str(Path(file_path).parent)
    try:
        git_check = subprocess.run(
            ["git", "ls-files", "--error-unmatch", file_path],
            check=False,
            capture_output=True,
            text=True,
            cwd=containing_directory,
            timeout=GIT_LS_FILES_TIMEOUT_SECONDS,
            env=_build_git_command_environment(),
        )
        return git_check.returncode != 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _build_git_command_environment() -> dict[str, str]:
    return {
        each_name: each_value
        for each_name, each_value in os.environ.items()
        if not each_name.upper().startswith("GIT_")
    }


def _is_path_under_directory(candidate_path: str, directory_path: str) -> bool:
    try:
        return os.path.commonpath((candidate_path, directory_path)) == directory_path
    except ValueError:
        return False


def is_protected_path(file_path: str) -> bool:
    lexical_hooks_directory = os.path.normcase(os.path.abspath(HOOKS_DIR))
    lexical_candidate_path = os.path.normcase(os.path.abspath(file_path))
    resolved_hooks_directory = os.path.normcase(os.path.realpath(HOOKS_DIR))
    resolved_candidate_path = os.path.normcase(os.path.realpath(file_path))
    return _is_path_under_directory(
        lexical_candidate_path, lexical_hooks_directory
    ) or _is_path_under_directory(resolved_candidate_path, resolved_hooks_directory)


def formatter_name_for_path(file_path: str) -> str | None:
    suffix = Path(file_path).suffix.lower()
    if suffix in PYTHON_EXTENSIONS:
        return PYTHON_FORMATTER_NAME
    if suffix in JS_EXTENSIONS or suffix in JSON_EXTENSIONS:
        if has_prettier_config(file_path):
            return PRETTIER_FORMATTER_NAME
    return None


def is_formatter_eligible(tool_name: str, file_path: str) -> bool:
    if tool_name != WRITE_TOOL_NAME or not file_path:
        return False
    if is_protected_path(file_path) or not is_untracked_in_git(file_path):
        return False
    return formatter_name_for_path(file_path) is not None


def _write_command_diagnostic(file_path: str, command: list[str], diagnostic_text: str) -> None:
    normalized_diagnostic = diagnostic_text.strip()
    if not normalized_diagnostic:
        return
    command_text = " ".join(command)
    sys.stderr.write(
        FORMATTER_DIAGNOSTIC_TEMPLATE % (file_path, f"{command_text}: {normalized_diagnostic}")
    )


def _combine_command_diagnostics(
    completed_process: subprocess.CompletedProcess[str],
) -> str:
    all_diagnostics = [
        each_stream.strip()
        for each_stream in (completed_process.stdout, completed_process.stderr)
        if each_stream
    ]
    return FORMATTER_DIAGNOSTIC_SEPARATOR.join(all_diagnostics)


def _run_command(
    command: list[str], file_path: str, timeout_seconds: int
) -> tuple[subprocess.CompletedProcess[str] | None, bool]:
    try:
        completed_process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return None, False
    except subprocess.TimeoutExpired:
        sys.stderr.write(FORMATTER_TIMEOUT_DIAGNOSTIC_TEMPLATE % (file_path, timeout_seconds))
        return None, True

    if completed_process.returncode != 0:
        _write_command_diagnostic(
            file_path,
            command,
            _combine_command_diagnostics(completed_process),
        )
    return completed_process, False


def _run_python_fix_commands(file_path: str) -> None:
    all_fix_commands = [
        ["ruff", "check", "--fix", file_path],
        [sys.executable, "-m", "ruff", "check", "--fix", file_path],
    ]
    for each_command in all_fix_commands:
        completed_process, did_timeout = _run_command(
            each_command, file_path, PYTHON_FORMAT_TIMEOUT_SECONDS
        )
        if did_timeout or completed_process is not None:
            return


def _run_python_format_commands(file_path: str) -> None:
    all_format_commands = [
        ["ruff", "format", file_path],
        [sys.executable, "-m", "ruff", "format", file_path],
        ["black", file_path],
        [sys.executable, "-m", "black", file_path],
    ]
    for each_command in all_format_commands:
        completed_process, did_timeout = _run_command(
            each_command, file_path, PYTHON_FORMAT_TIMEOUT_SECONDS
        )
        if did_timeout:
            return
        if completed_process is not None and completed_process.returncode == 0:
            send_format_notification(file_path, formatter_name_for_command(each_command))
            return


def formatter_name_for_command(command: list[str]) -> str:
    if command[0] == sys.executable:
        return command[2]
    return command[0]


def _run_prettier(file_path: str) -> None:
    prettier_command = [
        NPX_EXECUTABLE,
        "--yes",
        "prettier",
        "--write",
        os.path.realpath(file_path),
    ]
    completed_process, _did_timeout = _run_command(
        prettier_command, file_path, JS_FORMAT_TIMEOUT_SECONDS
    )
    if completed_process is not None and completed_process.returncode == 0:
        send_format_notification(file_path, PRETTIER_FORMATTER_NAME)


def run_eligible_formatter(file_path: str) -> None:
    formatter_name = formatter_name_for_path(file_path)
    if formatter_name == PYTHON_FORMATTER_NAME:
        _run_python_fix_commands(file_path)
        _run_python_format_commands(file_path)
        return
    if formatter_name == PRETTIER_FORMATTER_NAME:
        _run_prettier(file_path)


def _read_hook_input() -> dict[str, object] | None:
    try:
        parsed_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed_input, dict):
        return None
    return parsed_input


def _read_string_field(field_source: Mapping[str, object], field_name: str) -> str:
    field_value = field_source.get(field_name)
    return field_value if isinstance(field_value, str) else ""


def _read_hook_file_path(hook_input: Mapping[str, object]) -> str:
    tool_input = hook_input.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    return _read_string_field(tool_input, "file_path")


def main() -> None:
    hook_input = _read_hook_input()
    if hook_input is None:
        return

    tool_name = _read_string_field(hook_input, "tool_name")
    file_path = _read_hook_file_path(hook_input)
    if not is_formatter_eligible(tool_name, file_path):
        return
    run_eligible_formatter(file_path)


if __name__ == "__main__":
    main()
