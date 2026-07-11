"""Tests for bugteam_fix_hookspath auto-remediation.

Covers:
- removes a local-scope core.hooksPath override and re-runs preflight
- sets global core.hooksPath when missing
- idempotent: second invocation produces the same final state with no errors
- no-op when no override exists and global is already canonical
- exits non-zero with a clear message when canonical hooks dir is missing
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest


def _load_fix_module() -> ModuleType:
    module_path = Path(__file__).parent / "bugteam_fix_hookspath.py"
    spec = importlib.util.spec_from_file_location("bugteam_fix_hookspath", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bugteam_fix_hookspath = _load_fix_module()


def _make_isolated_git_environment(home_directory: Path) -> dict[str, str]:
    """Build an env dict that pins git's HOME and XDG paths into a tmp directory.

    Without this, real `git config --global` reads/writes hit the developer's
    actual ~/.gitconfig — which would corrupt the host machine and make tests
    depend on global state. Pointing HOME, USERPROFILE, and XDG_CONFIG_HOME
    at a temp directory isolates the test fully on every supported git
    version. GIT_CONFIG_GLOBAL would tighten the binding but requires
    git >= 2.32 (August 2021); HOME/USERPROFILE already isolate on older git.
    """
    isolated_environment = os.environ.copy()
    isolated_environment["HOME"] = str(home_directory)
    isolated_environment["USERPROFILE"] = str(home_directory)
    isolated_environment["XDG_CONFIG_HOME"] = str(home_directory / ".config")
    isolated_environment["GIT_CONFIG_NOSYSTEM"] = "1"
    return isolated_environment


def _initialize_repository(repository_path: Path, environment: dict[str, str]) -> None:
    repository_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--quiet", str(repository_path)],
        check=True,
        env=environment,
    )


def _set_local_hooks_path(
    repository_path: Path,
    hooks_path_value: str,
    environment: dict[str, str],
) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repository_path),
            "config",
            "--local",
            "core.hooksPath",
            hooks_path_value,
        ],
        check=True,
        env=environment,
    )


def _set_global_hooks_path(hooks_path_value: str, environment: dict[str, str]) -> None:
    subprocess.run(
        ["git", "config", "--global", "core.hooksPath", hooks_path_value],
        check=True,
        env=environment,
    )


def _read_local_hooks_path(repository_path: Path, environment: dict[str, str]) -> str:
    completed_process = subprocess.run(
        [
            "git",
            "-C",
            str(repository_path),
            "config",
            "--local",
            "--get",
            "core.hooksPath",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    return completed_process.stdout.strip()


def _read_global_hooks_path(environment: dict[str, str]) -> str:
    completed_process = subprocess.run(
        ["git", "config", "--global", "--get", "core.hooksPath"],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    return completed_process.stdout.strip()


def _create_canonical_hooks_directory(home_directory: Path) -> Path:
    canonical_hooks_directory = home_directory / ".claude" / "hooks" / "git-hooks"
    canonical_hooks_directory.mkdir(parents=True)
    return canonical_hooks_directory


def test_should_remove_local_override_and_pass_preflight(tmp_path: Path) -> None:
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    canonical_hooks_directory = _create_canonical_hooks_directory(home_directory)
    _set_global_hooks_path(str(canonical_hooks_directory), environment)
    repository_path = tmp_path / "synthetic-repo"
    _initialize_repository(repository_path, environment)
    stale_local_value = str(repository_path / ".git" / "hooks")
    _set_local_hooks_path(repository_path, stale_local_value, environment)

    exit_code = bugteam_fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert exit_code == 0, (
        "fix script must succeed when canonical global hooks dir exists"
    )
    assert _read_local_hooks_path(repository_path, environment) == "", (
        "local core.hooksPath override must be removed"
    )


def test_should_set_global_hooks_path_when_missing(tmp_path: Path) -> None:
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    canonical_hooks_directory = _create_canonical_hooks_directory(home_directory)
    repository_path = tmp_path / "synthetic-repo"
    _initialize_repository(repository_path, environment)
    stale_local_value = str(repository_path / ".git" / "hooks")
    _set_local_hooks_path(repository_path, stale_local_value, environment)

    exit_code = bugteam_fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert exit_code == 0
    global_value_after_fix = _read_global_hooks_path(environment)
    assert (
        global_value_after_fix.replace("\\", "/")
        .rstrip("/")
        .endswith("hooks/git-hooks")
    ), (
        "fix script must set canonical global core.hooksPath when missing; "
        f"got '{global_value_after_fix}'"
    )


def test_should_be_idempotent(tmp_path: Path) -> None:
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    canonical_hooks_directory = _create_canonical_hooks_directory(home_directory)
    _set_global_hooks_path(str(canonical_hooks_directory), environment)
    repository_path = tmp_path / "synthetic-repo"
    _initialize_repository(repository_path, environment)
    stale_local_value = str(repository_path / ".git" / "hooks")
    _set_local_hooks_path(repository_path, stale_local_value, environment)

    first_exit_code = bugteam_fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )
    second_exit_code = bugteam_fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert first_exit_code == 0
    assert second_exit_code == 0, "second invocation must succeed without errors"
    assert _read_local_hooks_path(repository_path, environment) == ""


def test_should_no_op_when_already_clean(tmp_path: Path) -> None:
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    canonical_hooks_directory = _create_canonical_hooks_directory(home_directory)
    _set_global_hooks_path(str(canonical_hooks_directory), environment)
    repository_path = tmp_path / "synthetic-repo"
    _initialize_repository(repository_path, environment)

    exit_code = bugteam_fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert exit_code == 0
    assert _read_local_hooks_path(repository_path, environment) == ""
    assert (
        _read_global_hooks_path(environment)
        .replace("\\", "/")
        .rstrip("/")
        .endswith("hooks/git-hooks")
    )


def test_should_exit_nonzero_when_canonical_hooks_directory_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    repository_path = tmp_path / "synthetic-repo"
    _initialize_repository(repository_path, environment)
    stale_local_value = str(repository_path / ".git" / "hooks")
    _set_local_hooks_path(repository_path, stale_local_value, environment)

    exit_code = bugteam_fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert exit_code != 0, (
        "fix script must fail clearly when ~/.claude/hooks/git-hooks does not exist "
        "so the user knows to run `npx claude-dev-env .`"
    )
    captured_streams = capsys.readouterr()
    assert "hooks/git-hooks" in captured_streams.err.replace("\\", "/")


def test_should_handle_paths_with_spaces(tmp_path: Path) -> None:
    home_directory = tmp_path / "home with space"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    canonical_hooks_directory = _create_canonical_hooks_directory(home_directory)
    _set_global_hooks_path(str(canonical_hooks_directory), environment)
    repository_path = tmp_path / "repo with space"
    _initialize_repository(repository_path, environment)
    stale_local_value = str(repository_path / ".git" / "hooks")
    _set_local_hooks_path(repository_path, stale_local_value, environment)

    exit_code = bugteam_fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert exit_code == 0
    assert _read_local_hooks_path(repository_path, environment) == ""


def test_list_local_core_hooks_path_values_raises_on_unexpected_git_failure(
    tmp_path: Path,
) -> None:
    """A non-empty stderr from git config must propagate as an error.

    Regression for loop1-5: returning [] on every non-zero git exit collapses
    "key unset" with "git failed for some other reason" — the caller then
    skips the unset call, leaving a stale local override in place.
    """
    repository_path = tmp_path / "repo"
    repository_path.mkdir()

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[],
            returncode=128,
            stdout="",
            stderr="fatal: unable to read config file: permission denied\n",
        )

    with patch.object(subprocess, "run", fake_run):
        with pytest.raises(RuntimeError):
            bugteam_fix_hookspath.list_local_core_hooks_path_values(
                repository_path,
                None,
            )


def test_read_global_core_hooks_path_raises_on_unexpected_git_failure() -> None:
    """A non-empty stderr from git config must propagate as an error.

    Regression for loop1-6: returning "" on every non-zero git exit conflates
    "global hooksPath unset" with "git failed for some other reason" — the
    caller then overwrites global git config based on a non-truthful read.
    """

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[],
            returncode=128,
            stdout="",
            stderr="fatal: bad config line\n",
        )

    with patch.object(subprocess, "run", fake_run):
        with pytest.raises(RuntimeError):
            bugteam_fix_hookspath.read_global_core_hooks_path(None)


def test_list_local_core_hooks_path_values_returns_empty_when_key_unset(
    tmp_path: Path,
) -> None:
    """Genuine key-unset (exit 1 + empty stderr) must continue to return []."""
    repository_path = tmp_path / "repo"
    repository_path.mkdir()

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="",
        )

    with patch.object(subprocess, "run", fake_run):
        result = bugteam_fix_hookspath.list_local_core_hooks_path_values(
            repository_path,
            None,
        )
    assert result == []


def test_read_global_core_hooks_path_returns_empty_when_key_unset() -> None:
    """Genuine key-unset (exit 1 + empty stderr) must continue to return ''."""

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="",
        )

    with patch.object(subprocess, "run", fake_run):
        result = bugteam_fix_hookspath.read_global_core_hooks_path(None)
    assert result == ""
