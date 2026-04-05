#!/usr/bin/env python3

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


PYTHON_EXTENSIONS = {".py"}
JS_EXTENSIONS = {".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"}
JSON_EXTENSIONS = {".json"}
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOKS_DIR = os.path.join(PLUGIN_ROOT, "hooks") + os.sep
PYTHON_FORMAT_TIMEOUT_SECONDS = 15
JS_FORMAT_TIMEOUT_SECONDS = 30
PRETTIER_CONFIG_NAMES = {
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


def has_prettier_config(file_path: str) -> bool:
    each_ancestor = Path(file_path).resolve().parent
    while True:
        for config_name in PRETTIER_CONFIG_NAMES:
            if (each_ancestor / config_name).exists():
                return True
        parent = each_ancestor.parent
        if parent == each_ancestor:
            break
        each_ancestor = parent
    return False


def is_untracked_in_git(file_path: str) -> bool:
    """Check if file is untracked (brand new) by git."""
    containing_directory = str(Path(file_path).parent)
    try:
        git_check = subprocess.run(
            ["git", "ls-files", "--error-unmatch", file_path],
            capture_output=True,
            text=True,
            cwd=containing_directory,
            timeout=5,
        )
        return git_check.returncode != 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    file_path = hook_input.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    if tool_name == "Edit":
        sys.exit(0)

    if tool_name == "Write" and not is_untracked_in_git(file_path):
        sys.exit(0)

    if file_path.startswith(HOOKS_DIR):
        sys.exit(0)

    suffix = Path(file_path).suffix.lower()

    if suffix in PYTHON_EXTENSIONS:
        for each_formatter_command in [
            ["ruff", "format", file_path],
            [sys.executable, "-m", "ruff", "format", file_path],
            ["black", file_path],
            [sys.executable, "-m", "black", file_path],
        ]:
            try:
                format_run = subprocess.run(each_formatter_command, capture_output=True, text=True, timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)
                if format_run.returncode == 0:
                    formatter_name = each_formatter_command[0] if each_formatter_command[0] != sys.executable else each_formatter_command[2]
                    send_format_notification(file_path, formatter_name)
                    break
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                break
    elif suffix in JS_EXTENSIONS or suffix in JSON_EXTENSIONS:
        if not has_prettier_config(file_path):
            sys.exit(0)
        try:
            prettier_run = subprocess.run(
                ["npx", "--yes", "prettier", "--write", file_path],
                capture_output=True,
                text=True,
                timeout=JS_FORMAT_TIMEOUT_SECONDS,
            )
            if prettier_run.returncode == 0:
                send_format_notification(file_path, "prettier")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
