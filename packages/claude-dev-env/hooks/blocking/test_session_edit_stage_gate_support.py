"""Production-neutral fixtures for session-edit stage gate tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SUPPORT_DIRECTORY = Path(__file__).resolve().parent
_HOOKS_TREE = _SUPPORT_DIRECTORY.parent
if str(_HOOKS_TREE) not in sys.path:
    sys.path.insert(0, str(_HOOKS_TREE))

from hooks_constants.session_edit_stage_gate_constants import (  # noqa: E402
    ALL_EDITED_FILE_PATHS_KEY,
    SESSION_EDIT_FILE_PREFIX,
    SESSION_EDIT_FILE_SUFFIX,
)


def clean_git_environment() -> dict[str, str]:
    """Return the environment without inherited repository overrides."""
    return {
        each_key: each_value
        for each_key, each_value in os.environ.items()
        if not each_key.startswith("GIT_")
    }


def run_git(repository_root: Path, *git_arguments: str) -> None:
    """Run one Git command in a test repository."""
    subprocess.run(
        ["git", "-C", str(repository_root), *git_arguments],
        check=True,
        capture_output=True,
        env=clean_git_environment(),
    )


def initialize_repository(repository_root: Path) -> None:
    """Create a Git repository on a non-protected test branch."""
    run_git(repository_root, "init")
    run_git(repository_root, "checkout", "-b", "test-session-stage")
    run_git(repository_root, "config", "user.email", "tests@example.com")
    run_git(repository_root, "config", "user.name", "Gate Tests")


def prepare_repository_with_unstaged_edit(repository_root: Path) -> Path:
    """Create one tracked file with an unstaged edit."""
    initialize_repository(repository_root)
    tracked_file = repository_root / "widget.py"
    tracked_file.write_text("x = 1\n", encoding="utf-8")
    run_git(repository_root, "add", "widget.py")
    run_git(repository_root, "commit", "-m", "add widget")
    tracked_file.write_text("x = 2\n", encoding="utf-8")
    return tracked_file


def prepare_repository_with_two_unstaged_edits(repository_root: Path) -> tuple[Path, Path]:
    """Create two tracked files with separate unstaged edits."""
    initialize_repository(repository_root)
    tracked_file = repository_root / "widget.py"
    second_file = repository_root / "second_widget.py"
    tracked_file.write_text("x = 1\n", encoding="utf-8")
    second_file.write_text("y = 1\n", encoding="utf-8")
    run_git(repository_root, "add", "widget.py", "second_widget.py")
    run_git(repository_root, "commit", "-m", "add widgets")
    tracked_file.write_text("x = 2\n", encoding="utf-8")
    second_file.write_text("y = 2\n", encoding="utf-8")
    return tracked_file, second_file


def make_test_directories(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create repository, tracker, and home directories for one test."""
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    temp_directory = tmp_path / "tmp"
    temp_directory.mkdir()
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    return repository_root, temp_directory, home_directory


def make_process_repository(tmp_path: Path) -> Path:
    """Create a separate Git repository for the dispatcher process directory."""
    process_repository = tmp_path / "process-repository"
    process_repository.mkdir()
    initialize_repository(process_repository)
    return process_repository


def prepare_process_child_repository(process_repository: Path) -> None:
    """Create the relative command directory inside process repository B."""
    process_child_repository = process_repository / "child"
    process_child_repository.mkdir()
    initialize_repository(process_child_repository)


def build_hook_environment(
    temp_directory: Path,
    home_directory: Path,
) -> dict[str, str]:
    """Build isolated environment variables for production hooks."""
    environment = clean_git_environment()
    environment["TMP"] = str(temp_directory)
    environment["TEMP"] = str(temp_directory)
    environment["TMPDIR"] = str(temp_directory)
    environment["USERPROFILE"] = str(home_directory)
    environment["HOME"] = str(home_directory)
    return environment


def run_production_hook(
    hook_path: Path,
    payload: str,
    repository_root: Path,
    temp_directory: Path,
    home_directory: Path,
    process_directory: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one hook script as a production subprocess."""
    return subprocess.run(
        [sys.executable, str(hook_path)],
        check=False,
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(process_directory or repository_root),
        env=build_hook_environment(temp_directory, home_directory),
        timeout=60,
    )


def run_tracker_event(
    tracked_file: Path,
    session_id: str,
    repository_root: Path,
    temp_directory: Path,
    home_directory: Path,
) -> subprocess.CompletedProcess[str]:
    """Run the production PostToolUse tracker for one edited file."""
    payload = json.dumps(
        {
            "tool_name": "Edit",
            "session_id": session_id,
            "tool_input": {"file_path": str(tracked_file)},
        }
    )
    return run_production_hook(
        _HOOKS_TREE / "observability" / "session_file_edit_tracker.py",
        payload,
        repository_root,
        temp_directory,
        home_directory,
    )


def run_bash_dispatcher(
    bash_command: str,
    session_id: str,
    repository_root: Path,
    temp_directory: Path,
    home_directory: Path,
    process_directory: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the production Bash PreToolUse dispatcher for one command."""
    payload = json.dumps(
        {
            "tool_name": "Bash",
            "cwd": str(repository_root),
            "session_id": session_id,
            "tool_input": {"command": bash_command},
        }
    )
    return run_production_hook(
        _SUPPORT_DIRECTORY / "bash_pre_tool_use_dispatcher.py",
        payload,
        repository_root,
        temp_directory,
        home_directory,
        process_directory,
    )


def read_tracker_paths(temp_directory: Path, session_id: str) -> list[str]:
    """Read the recorded paths from one production tracker file."""
    tracker_file = (
        temp_directory / f"{SESSION_EDIT_FILE_PREFIX}{session_id}{SESSION_EDIT_FILE_SUFFIX}"
    )
    tracker_payload = json.loads(tracker_file.read_text(encoding="utf-8"))
    return tracker_payload[ALL_EDITED_FILE_PATHS_KEY]


def parse_dispatcher_decision(stdout_text: str) -> tuple[str, str]:
    """Return the dispatcher decision and reason from its stdout payload."""
    if not stdout_text.strip():
        return "", ""
    hook_specific_output = json.loads(stdout_text)["hookSpecificOutput"]
    return (
        hook_specific_output.get("permissionDecision", ""),
        hook_specific_output.get("permissionDecisionReason", ""),
    )
