"""Tests for the hookless sandbox launcher."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from prototype_scripts_constants.config.launch_sandbox_constants import (
    BARE_FLAG,
    CLAUDE_EXECUTABLE_NAME,
    LAUNCH_MISSING_PATH_EXIT_CODE,
    PROMPT_FLAG,
    SETTINGS_FLAG,
    SKIP_PERMISSIONS_FLAG,
)

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
LAUNCHER_PATH = SCRIPTS_DIRECTORY / "launch_sandbox.py"

SANDBOX_TASK_TEXT = "Build a proof of concept for the widget cache."
SANDBOX_TIMEOUT_SECONDS = 42
FAKE_RUNNER_EXIT_CODE = 7


def load_launcher_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("launch_sandbox", LAUNCHER_PATH)
    assert spec is not None
    assert spec.loader is not None
    launcher_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher_module)
    return launcher_module


class RecordingCommandRunner:
    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code
        self.recorded_tokens: list[str] = []
        self.recorded_working_directory: Path | None = None
        self.recorded_timeout_seconds: int | None = None
        self.call_count = 0

    def __call__(
        self,
        all_command_tokens: list[str],
        working_directory: Path,
        timeout_seconds: int | None,
    ) -> int:
        self.call_count += 1
        self.recorded_tokens = all_command_tokens
        self.recorded_working_directory = working_directory
        self.recorded_timeout_seconds = timeout_seconds
        return self.exit_code


def make_sandbox_worktree(tmp_path: Path) -> tuple[Path, Path]:
    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()
    settings_path = tmp_path / "sandbox-settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    return worktree_path, settings_path


def make_task_file(tmp_path: Path) -> Path:
    task_file_path = tmp_path / "task.txt"
    task_file_path.write_text(SANDBOX_TASK_TEXT, encoding="utf-8")
    return task_file_path


def test_build_sandbox_command_has_the_exact_ordered_argv() -> None:
    launcher = load_launcher_module()
    settings_path = Path("/tmp/sandbox-settings.json")
    sandbox_command = launcher.build_sandbox_command(SANDBOX_TASK_TEXT, settings_path)
    assert sandbox_command == [
        CLAUDE_EXECUTABLE_NAME,
        PROMPT_FLAG,
        SANDBOX_TASK_TEXT,
        BARE_FLAG,
        SKIP_PERMISSIONS_FLAG,
        SETTINGS_FLAG,
        str(settings_path),
    ]


def test_run_sandbox_records_cwd_and_argv_without_launching_claude(
    tmp_path: Path,
) -> None:
    launcher = load_launcher_module()
    worktree_path, settings_path = make_sandbox_worktree(tmp_path)
    recording_runner = RecordingCommandRunner(FAKE_RUNNER_EXIT_CODE)
    exit_code = launcher.run_sandbox(
        worktree_path,
        settings_path,
        SANDBOX_TASK_TEXT,
        SANDBOX_TIMEOUT_SECONDS,
        recording_runner,
    )
    assert exit_code == FAKE_RUNNER_EXIT_CODE
    assert recording_runner.call_count == 1
    assert recording_runner.recorded_working_directory == worktree_path
    assert recording_runner.recorded_tokens == launcher.build_sandbox_command(
        SANDBOX_TASK_TEXT, settings_path
    )
    assert recording_runner.recorded_timeout_seconds == SANDBOX_TIMEOUT_SECONDS


def test_validate_sandbox_paths_passes_when_every_path_exists(tmp_path: Path) -> None:
    launcher = load_launcher_module()
    worktree_path, settings_path = make_sandbox_worktree(tmp_path)
    task_file_path = make_task_file(tmp_path)
    error_message = launcher.validate_sandbox_paths(
        worktree_path, settings_path, task_file_path
    )
    assert error_message is None


def test_validate_sandbox_paths_reports_a_missing_worktree(tmp_path: Path) -> None:
    launcher = load_launcher_module()
    _, settings_path = make_sandbox_worktree(tmp_path)
    task_file_path = make_task_file(tmp_path)
    error_message = launcher.validate_sandbox_paths(
        tmp_path / "absent-worktree", settings_path, task_file_path
    )
    assert error_message is not None
    assert "worktree" in error_message


def test_validate_sandbox_paths_reports_a_missing_task_file(tmp_path: Path) -> None:
    launcher = load_launcher_module()
    worktree_path, settings_path = make_sandbox_worktree(tmp_path)
    error_message = launcher.validate_sandbox_paths(
        worktree_path, settings_path, tmp_path / "absent-task.txt"
    )
    assert error_message is not None
    assert "task file" in error_message


def test_validate_sandbox_paths_reports_a_missing_settings_file(tmp_path: Path) -> None:
    launcher = load_launcher_module()
    worktree_path, _ = make_sandbox_worktree(tmp_path)
    task_file_path = make_task_file(tmp_path)
    error_message = launcher.validate_sandbox_paths(
        worktree_path, tmp_path / "absent-settings.json", task_file_path
    )
    assert error_message is not None
    assert "settings" in error_message


def test_main_returns_the_missing_path_exit_code_for_an_absent_worktree(
    tmp_path: Path,
) -> None:
    launcher = load_launcher_module()
    _, settings_path = make_sandbox_worktree(tmp_path)
    task_file_path = make_task_file(tmp_path)
    exit_code = launcher.main(
        [
            "--worktree",
            str(tmp_path / "absent-worktree"),
            "--settings",
            str(settings_path),
            "--task-file",
            str(task_file_path),
        ]
    )
    assert exit_code == LAUNCH_MISSING_PATH_EXIT_CODE


def test_main_runs_the_sandbox_and_returns_the_runner_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = load_launcher_module()
    worktree_path, settings_path = make_sandbox_worktree(tmp_path)
    task_file_path = make_task_file(tmp_path)
    recording_runner = RecordingCommandRunner(FAKE_RUNNER_EXIT_CODE)
    monkeypatch.setattr(launcher, "_run_via_subprocess", recording_runner)
    exit_code = launcher.main(
        [
            "--worktree",
            str(worktree_path),
            "--settings",
            str(settings_path),
            "--task-file",
            str(task_file_path),
        ]
    )
    assert exit_code == FAKE_RUNNER_EXIT_CODE
    assert recording_runner.call_count == 1
    assert recording_runner.recorded_working_directory == worktree_path.resolve()


def test_main_resolves_a_relative_settings_path_to_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = load_launcher_module()
    worktree_path, settings_path = make_sandbox_worktree(tmp_path)
    task_file_path = make_task_file(tmp_path)
    recording_runner = RecordingCommandRunner(FAKE_RUNNER_EXIT_CODE)
    monkeypatch.setattr(launcher, "_run_via_subprocess", recording_runner)
    monkeypatch.chdir(tmp_path)
    launcher.main(
        [
            "--worktree",
            worktree_path.name,
            "--settings",
            settings_path.name,
            "--task-file",
            task_file_path.name,
        ]
    )
    recorded_settings_token = recording_runner.recorded_tokens[-1]
    assert Path(recorded_settings_token).is_absolute()
    assert Path(recorded_settings_token) == settings_path.resolve()
    assert recording_runner.recorded_working_directory == worktree_path.resolve()
