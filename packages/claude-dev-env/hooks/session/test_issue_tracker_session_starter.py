"""Tests for issue_tracker_session_starter — SessionStart injector for the tracker.

Each test drives the real ``main()`` with a JSON payload on stdin through the
production gates: a real temporary git repository for the GitHub-remote probe and
a real temporary ``~/.claude`` tree for the skill and agent presence probe.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import issue_tracker_session_starter as starter
import pytest
from hooks_constants.issue_tracker_session_starter_constants import (
    CLAUDE_CONFIG_DIRECTORY_NAME,
    ISSUE_TRACKER_ENV_VAR_NAME,
    ALL_ISSUE_TRACKER_PRESENCE_PATH_FRAGMENTS,
    ISSUE_TRACKER_START_DIRECTIVE,
)
from hooks_constants.session_start_injector_constants import (
    ADDITIONAL_CONTEXT_KEY,
    HOOK_EVENT_NAME_KEY,
    HOOK_SPECIFIC_OUTPUT_KEY,
    SESSION_START_EVENT_NAME,
)

_GITHUB_REMOTE_URL = "https://github.com/example-owner/example-repo.git"
_STARTUP_SOURCE = "startup"


def _init_github_repo(repo_directory: Path) -> None:
    """Create a git repository whose origin remote points at a GitHub URL."""
    for each_git_command in (
        ["git", "init"],
        ["git", "remote", "add", "origin", _GITHUB_REMOTE_URL],
    ):
        subprocess.run(each_git_command, cwd=repo_directory, check=True, capture_output=True)


def _install_tracker_files(home_directory: Path) -> None:
    """Write the tracker skill and agent probe files under a fake ~/.claude tree."""
    for each_fragment in ALL_ISSUE_TRACKER_PRESENCE_PATH_FRAGMENTS:
        target_file = home_directory / CLAUDE_CONFIG_DIRECTORY_NAME / each_fragment
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("present", encoding="utf-8")


def _point_home_at(monkeypatch: pytest.MonkeyPatch, home_directory: Path) -> None:
    """Redirect ``Path.home()`` at the given directory for the duration of a test."""
    monkeypatch.setenv("HOME", str(home_directory))
    monkeypatch.setenv("USERPROFILE", str(home_directory))


def _setup_eligible_repo_and_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a GitHub-remote repo and a ~/.claude tree with both tracker files present.

    Returns the repo directory so the caller's payload can point ``cwd`` at it.
    """
    repo_directory = tmp_path / "repo"
    repo_directory.mkdir()
    _init_github_repo(repo_directory)
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    _install_tracker_files(home_directory)
    _point_home_at(monkeypatch, home_directory)
    return repo_directory


def test_enabled_start_emits_the_nested_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_hook_main_with_payload: Callable[[ModuleType, dict[str, object]], str],
) -> None:
    repo_directory = _setup_eligible_repo_and_home(tmp_path, monkeypatch)
    monkeypatch.delenv(ISSUE_TRACKER_ENV_VAR_NAME, raising=False)

    emitted = json.loads(
        run_hook_main_with_payload(
            starter, {"source": _STARTUP_SOURCE, "cwd": str(repo_directory)}
        )
    )

    nested_output = emitted[HOOK_SPECIFIC_OUTPUT_KEY]
    assert nested_output[HOOK_EVENT_NAME_KEY] == SESSION_START_EVENT_NAME
    assert nested_output[ADDITIONAL_CONTEXT_KEY] == ISSUE_TRACKER_START_DIRECTIVE
    assert ADDITIONAL_CONTEXT_KEY not in emitted


def test_toggle_off_stays_silent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_hook_main_with_payload: Callable[[ModuleType, dict[str, object]], str],
) -> None:
    repo_directory = _setup_eligible_repo_and_home(tmp_path, monkeypatch)
    monkeypatch.setenv(ISSUE_TRACKER_ENV_VAR_NAME, "off")

    output = run_hook_main_with_payload(
        starter, {"source": _STARTUP_SOURCE, "cwd": str(repo_directory)}
    )

    assert output.strip() == ""


@pytest.mark.parametrize("ineligible_source", ["resume", "compact"])
def test_ineligible_source_stays_silent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_hook_main_with_payload: Callable[[ModuleType, dict[str, object]], str],
    ineligible_source: str,
) -> None:
    repo_directory = _setup_eligible_repo_and_home(tmp_path, monkeypatch)
    monkeypatch.delenv(ISSUE_TRACKER_ENV_VAR_NAME, raising=False)

    output = run_hook_main_with_payload(
        starter, {"source": ineligible_source, "cwd": str(repo_directory)}
    )

    assert output.strip() == ""


def test_no_github_remote_stays_silent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_hook_main_with_payload: Callable[[ModuleType, dict[str, object]], str],
) -> None:
    plain_directory = tmp_path / "plain"
    plain_directory.mkdir()
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    _install_tracker_files(home_directory)
    _point_home_at(monkeypatch, home_directory)
    monkeypatch.delenv(ISSUE_TRACKER_ENV_VAR_NAME, raising=False)

    output = run_hook_main_with_payload(
        starter, {"source": _STARTUP_SOURCE, "cwd": str(plain_directory)}
    )

    assert output.strip() == ""


def test_tracker_files_absent_stays_silent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_hook_main_with_payload: Callable[[ModuleType, dict[str, object]], str],
) -> None:
    repo_directory = tmp_path / "repo"
    repo_directory.mkdir()
    _init_github_repo(repo_directory)
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    _point_home_at(monkeypatch, home_directory)
    monkeypatch.delenv(ISSUE_TRACKER_ENV_VAR_NAME, raising=False)

    output = run_hook_main_with_payload(
        starter, {"source": _STARTUP_SOURCE, "cwd": str(repo_directory)}
    )

    assert output.strip() == ""


def test_build_issue_tracker_directive_returns_the_shared_constant() -> None:
    assert starter.build_issue_tracker_directive() == ISSUE_TRACKER_START_DIRECTIVE
