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
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from types import ModuleType

_hooks_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_notification_utils_directory = os.path.join(_hooks_directory, "notification")
sys.path.insert(0, _notification_utils_directory)

_validators_directory = os.path.join(_hooks_directory, "validators")
if _validators_directory not in sys.path:
    sys.path.insert(0, _validators_directory)

if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from mypy_integration import find_pyproject_with_mypy_config  # noqa: E402

from hooks_constants.mypy_validator_cache_constants import (  # noqa: E402
    CACHE_FILE_ENCODING,
    CONTENT_HASH_CACHE_PASSING_EXIT_CODE,
    HOOK_STATE_CACHE_DIRECTORY,
    MYPY_CONFIG_CACHE_FILENAME,
    MYPY_CONTENT_HASH_CACHE_FILENAME,
    SESSION_ID_ENVIRONMENT_VARIABLE,
    UNKNOWN_SESSION_IDENTIFIER,
)


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


_session_config_cache_by_project_root: dict[str, str | None] = {}


def reset_session_config_cache() -> None:
    """Clear the in-process config-walk cache so the next walk runs fresh.

    The cache is normally seeded once per project root per session; tests call
    this between scenarios so a redirected cache directory starts empty.
    """
    _session_config_cache_by_project_root.clear()


def resolve_session_identifier() -> str:
    """Return the current session identifier for keying per-session caches.

    Returns:
        The ``CLAUDE_CODE_SESSION_ID`` environment value, or a fixed unknown
        marker when the variable is unset or empty so the cache still has a
        stable key within a single run.
    """
    session_identifier = os.environ.get(SESSION_ID_ENVIRONMENT_VARIABLE, "")
    return session_identifier or UNKNOWN_SESSION_IDENTIFIER


def _session_cache_path(cache_filename: str) -> Path:
    session_identifier = resolve_session_identifier()
    return Path(HOOK_STATE_CACHE_DIRECTORY) / session_identifier / cache_filename


def _read_cache_file(cache_path: Path) -> dict[str, object]:
    if not cache_path.is_file():
        return {}
    try:
        raw_text = cache_path.read_text(encoding=CACHE_FILE_ENCODING)
    except OSError:
        return {}
    if not raw_text.strip():
        return {}
    try:
        parsed_cache = json.loads(raw_text)
    except json.JSONDecodeError:
        return {}
    return parsed_cache if isinstance(parsed_cache, dict) else {}


def _write_cache_file(cache_path: Path, cache_by_key: dict[str, object]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(cache_by_key), encoding=CACHE_FILE_ENCODING
        )
    except OSError:
        return


def _walk_mypy_config(target_file: Path) -> Path | None:
    discovered_config = find_pyproject_with_mypy_config(target_file)
    return discovered_config if isinstance(discovered_config, Path) else None


def discover_mypy_config(target_file: Path, project_root: str) -> Path | None:
    """Return the nearest ancestor ``pyproject.toml`` that configures mypy.

    Mypy applies a project's ``[tool.mypy]`` settings only when the config file
    is on its invocation path; handing the discovered config to mypy lets a
    check run from the repository root still honor the project's own import
    resolution settings (such as ``ignore_missing_imports``) for a module that
    imports its siblings by name. The discovered config is cached per project
    root for the session, in process and in a session cache file, so a later
    edit under the same root reuses the result rather than walking ancestors
    again.

    Args:
        target_file: The Python file mypy will check.
        project_root: The directory mypy runs from; the cache key for the walk.

    Returns:
        The nearest ancestor ``pyproject.toml`` declaring a ``[tool.mypy]``
        table, or None when none exists above the file.
    """
    if project_root in _session_config_cache_by_project_root:
        cached_value = _session_config_cache_by_project_root[project_root]
        return Path(cached_value) if cached_value is not None else None

    config_cache_path = _session_cache_path(MYPY_CONFIG_CACHE_FILENAME)
    persisted_cache = _read_cache_file(config_cache_path)
    if project_root in persisted_cache:
        persisted_value = persisted_cache[project_root]
        resolved_persisted = persisted_value if isinstance(persisted_value, str) else None
        _session_config_cache_by_project_root[project_root] = resolved_persisted
        return Path(resolved_persisted) if resolved_persisted is not None else None

    discovered_config = _walk_mypy_config(target_file)
    discovered_value = str(discovered_config) if discovered_config is not None else None
    _session_config_cache_by_project_root[project_root] = discovered_value
    persisted_cache[project_root] = discovered_value
    _write_cache_file(config_cache_path, persisted_cache)
    return discovered_config


def _hash_file_contents(target_file: str) -> str | None:
    try:
        file_bytes = Path(target_file).read_bytes()
    except OSError:
        return None
    return hashlib.sha256(file_bytes).hexdigest()


def _read_cached_passing_hash(target_file: str) -> str | None:
    content_hash_cache = _read_cache_file(
        _session_cache_path(MYPY_CONTENT_HASH_CACHE_FILENAME)
    )
    cached_hash = content_hash_cache.get(target_file)
    return cached_hash if isinstance(cached_hash, str) else None


def _record_passing_hash(target_file: str, content_hash: str) -> None:
    content_hash_cache_path = _session_cache_path(MYPY_CONTENT_HASH_CACHE_FILENAME)
    content_hash_cache = _read_cache_file(content_hash_cache_path)
    content_hash_cache[target_file] = content_hash
    _write_cache_file(content_hash_cache_path, content_hash_cache)


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

    The mypy run is skipped when the target file's content hash matches the hash
    recorded the last time mypy passed for that file; that recorded skip can only
    return a pass, so a content change always re-runs mypy and a file edited to
    introduce a type error still blocks. The discovered config is reused from the
    per-session cache keyed by project root.

    The cache key is the target file's own bytes only, so the skip is blind to a
    cross-file change: when a dependency is edited in a way that breaks this
    file's call site and this file is later rewritten to its prior passing
    content, the cached pass returns without re-running mypy. The post-write hook
    already type-checks only the single edited file, so a dependent is never
    re-checked on the dependency's own edit regardless of the cache; the cache
    adds only the identical-rewrite skip on top of that existing single-file
    scope.

    Args:
        target_file: The absolute path of the file to type-check.
        project_root: The directory mypy runs from.

    Returns:
        The mypy exit code paired with its combined stdout and stderr text.
    """
    content_hash = _hash_file_contents(target_file)
    if content_hash is not None and content_hash == _read_cached_passing_hash(target_file):
        return CONTENT_HASH_CACHE_PASSING_EXIT_CODE, ""

    relative_file_path = os.path.relpath(target_file, project_root)
    mypy_config_file = discover_mypy_config(Path(target_file), project_root)
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

    if completed_process.returncode == CONTENT_HASH_CACHE_PASSING_EXIT_CODE and content_hash is not None:
        _record_passing_hash(target_file, content_hash)

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
