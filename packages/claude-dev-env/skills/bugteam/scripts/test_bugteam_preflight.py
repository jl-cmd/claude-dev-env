"""Tests for bugteam_preflight git hooks path verification.

Covers:
- core.hooksPath unset: exits non-zero with correction message
- core.hooksPath pointing to the correct claude hooks dir: exits zero
- core.hooksPath pointing elsewhere (husky override): exits non-zero
- core.hooksPath with trailing slash: must still pass after normalization
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def _load_preflight_module() -> ModuleType:
    module_path = Path(__file__).parent / "bugteam_preflight.py"
    spec = importlib.util.spec_from_file_location("bugteam_preflight", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bugteam_preflight = _load_preflight_module()


def _make_completed_process(
    stdout: str, returncode: int
) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = returncode
    return process


def test_should_exit_nonzero_when_core_hooks_path_unset(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=1)
        exit_code = bugteam_preflight.verify_git_hooks_path(Path("."))
    assert exit_code != 0
    captured = capsys.readouterr()
    assert "core.hooksPath" in captured.err
    assert "npx claude-dev-env" in captured.err or "git config" in captured.err


def test_should_exit_zero_when_core_hooks_path_points_to_claude_hooks(tmp_path: Path) -> None:
    claude_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    claude_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            str(claude_hooks_path) + "\n", returncode=0
        )
        exit_code = bugteam_preflight.verify_git_hooks_path(Path("."))
    assert exit_code == 0


def test_should_exit_nonzero_when_core_hooks_path_points_elsewhere(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "/some/other/path/.husky\n", returncode=0
        )
        exit_code = bugteam_preflight.verify_git_hooks_path(Path("."))
    assert exit_code != 0
    captured = capsys.readouterr()
    assert "core.hooksPath" in captured.err


def test_should_include_correction_commands_in_error_message(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=1)
        bugteam_preflight.verify_git_hooks_path(Path("."))
    captured = capsys.readouterr()
    assert (
        "npx claude-dev-env" in captured.err
        or "git config --global core.hooksPath" in captured.err
    )


def test_main_should_exit_nonzero_when_hooks_path_unset() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=1)
        exit_code = bugteam_preflight.main(["--no-pytest"])
    assert exit_code != 0


def test_main_should_continue_when_hooks_path_valid(tmp_path: Path) -> None:
    claude_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    claude_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            str(claude_hooks_path) + "\n", returncode=0
        )
        exit_code = bugteam_preflight.main(["--no-pytest"])
    assert exit_code == 0


def test_should_accept_hooks_path_with_trailing_slash() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "/home/user/.claude/hooks/git-hooks/\n", returncode=0
        )
        exit_code = bugteam_preflight.verify_git_hooks_path(Path("."))
    assert exit_code == 0, (
        "hooksPath with trailing slash must pass verification after normalization"
    )


def test_should_exit_zero_when_hooks_path_set_at_repo_scope(tmp_path: Path) -> None:
    claude_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    claude_hooks_path.mkdir(parents=True)
    repo_root = tmp_path / "my-repo"
    repo_root.mkdir()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            str(claude_hooks_path) + "\n", returncode=0
        )
        exit_code = bugteam_preflight.verify_git_hooks_path(repo_root)
    assert exit_code == 0, (
        "verify_git_hooks_path must accept a valid path returned by effective "
        "config query (not restricted to --global scope)"
    )
    called_command = mock_run.call_args[0][0]
    assert "--global" not in called_command, (
        "verify_git_hooks_path must query effective config, not --global only"
    )
    assert "-C" in called_command, (
        "verify_git_hooks_path must use git -C <repo_root> for repo-effective config"
    )
    dash_c_index = called_command.index("-C")
    assert called_command[dash_c_index + 1] == str(repo_root), (
        "git -C must receive the resolved repository root path"
    )


def test_verify_git_hooks_path_accepts_none_repository_root(tmp_path: Path) -> None:
    """When repository_root is None, the call must use git's cwd-effective config.

    Binds the documented optional contract: passing None must not raise and must
    omit the `-C <root>` arguments so git falls back to the working directory.
    """
    claude_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    claude_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            str(claude_hooks_path) + "\n", returncode=0
        )
        exit_code = bugteam_preflight.verify_git_hooks_path(None)
    assert exit_code == 0
    called_command = mock_run.call_args[0][0]
    assert "-C" not in called_command, (
        "verify_git_hooks_path(None) must omit -C so git uses cwd-effective config"
    )


def test_should_accept_hooks_path_with_backslash_and_trailing_slash() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "C:\\Users\\user\\.claude\\hooks\\git-hooks\\\n", returncode=0
        )
        exit_code = bugteam_preflight.verify_git_hooks_path(Path("."))
    assert exit_code == 0, (
        "Windows hooksPath with trailing backslash must pass after normalization"
    )


def test_should_exit_nonzero_when_git_executable_not_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Preflight must not crash with a traceback when git is missing from PATH."""
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        exit_code = bugteam_preflight.verify_git_hooks_path(Path("."))
    assert exit_code != 0, (
        "FileNotFoundError from subprocess.run must produce a non-zero exit, "
        "not a propagated traceback"
    )
    captured = capsys.readouterr()
    assert "git" in captured.err.lower(), (
        "Error message must mention git so the user knows what is missing"
    )
    assert (
        "npx claude-dev-env" in captured.err
        or "git config --global core.hooksPath" in captured.err
    ), "Error message must include the enforcement-absent remediation hints"


def test_should_exit_nonzero_when_subprocess_run_raises_os_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Preflight must surface a clean error for other OS-level git launch failures."""
    with patch("subprocess.run", side_effect=OSError("permission denied")):
        exit_code = bugteam_preflight.verify_git_hooks_path(Path("."))
    assert exit_code != 0, (
        "OSError from subprocess.run must produce a non-zero exit, "
        "not a propagated traceback"
    )
    captured = capsys.readouterr()
    assert "bugteam_preflight" in captured.err, (
        "Error message must be prefixed with the preflight tool name for context"
    )
    assert "permission denied" in captured.err, (
        "Error message must include the underlying OSError detail for diagnosis"
    )


def test_has_pytest_configuration_finds_pytest_ini(tmp_path: Path) -> None:
    """has_pytest_configuration must detect pytest.ini at the repo root.

    Regression for loop1-17/loop1-18: the literals "pytest.ini",
    "pyproject.toml", and "[tool.pytest" were inlined in production function
    bodies; centralizing them in bugteam_scripts_constants and importing here
    pins the contract.
    """
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    (repository_root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    assert bugteam_preflight.has_pytest_configuration(repository_root) is True


def test_has_pytest_configuration_finds_pyproject_pytest_section(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    (repository_root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\nminversion = '6.0'\n", encoding="utf-8"
    )
    assert bugteam_preflight.has_pytest_configuration(repository_root) is True


def test_has_pytest_configuration_returns_false_without_either_file(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    assert bugteam_preflight.has_pytest_configuration(repository_root) is False


def test_main_should_halt_when_env_var_lists_bugteam(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLAUDE_REVIEWS_DISABLED=bugteam must halt preflight with the dedicated exit code."""
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugteam")
    monkeypatch.delenv("BUGTEAM_PREFLIGHT_SKIP", raising=False)
    exit_code = bugteam_preflight.main(["--no-pytest"])
    assert exit_code == bugteam_preflight.EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV
    captured = capsys.readouterr()
    assert "CLAUDE_REVIEWS_DISABLED" in captured.err
    assert "bugteam" in captured.err


def test_main_should_continue_when_env_var_omits_bugteam(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """CLAUDE_REVIEWS_DISABLED without the bugteam token must not halt preflight."""
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot,bugbot")
    monkeypatch.delenv("BUGTEAM_PREFLIGHT_SKIP", raising=False)
    claude_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    claude_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            str(claude_hooks_path) + "\n", returncode=0
        )
        exit_code = bugteam_preflight.main(["--no-pytest"])
    assert exit_code != bugteam_preflight.EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV


def test_main_should_halt_when_env_var_contains_uppercase_or_whitespace_bugteam_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token matching must be case-insensitive and whitespace-tolerant."""
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", " BugTeam , copilot ")
    monkeypatch.delenv("BUGTEAM_PREFLIGHT_SKIP", raising=False)
    exit_code = bugteam_preflight.main(["--no-pytest"])
    assert exit_code == bugteam_preflight.EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV
