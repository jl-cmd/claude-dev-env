"""Tests for trigger_bugbot.

Covers:
- gh pr comment is invoked with --body-file (per gh-body-file rule)
- the body file written contains the literal phrase "bugbot run\\n"
- the comment URL emitted by gh is returned
- the temp body file is cleaned up
- subprocess errors propagate
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def _load_module() -> ModuleType:
    module_path = Path(__file__).parent / "trigger_bugbot.py"
    spec = importlib.util.spec_from_file_location("trigger_bugbot", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trigger_bugbot_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def test_should_invoke_gh_pr_comment_with_body_file_flag() -> None:
    captured_body_paths: list[str] = []

    def capture_body_file_contents(*subprocess_args, **_subprocess_kwargs):
        invoked_argv = subprocess_args[0]
        assert "--body-file" in invoked_argv
        body_file_path = invoked_argv[invoked_argv.index("--body-file") + 1]
        captured_body_paths.append(body_file_path)
        return _completed("https://github.com/acme/widget/issues/42#issuecomment-99\n")

    with patch("subprocess.run", side_effect=capture_body_file_contents) as mock_run:
        trigger_bugbot_module.trigger_bugbot(owner="acme", repo="widget", number=42)
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0:3] == ["gh", "pr", "comment"]
    assert "42" in invoked_argv
    assert "--repo" in invoked_argv
    assert "acme/widget" in invoked_argv


def test_should_write_literal_bugbot_run_phrase_into_body_file() -> None:
    captured_body_contents: list[str] = []

    def capture_body_file_contents(*subprocess_args, **_subprocess_kwargs):
        invoked_argv = subprocess_args[0]
        body_file_path = Path(invoked_argv[invoked_argv.index("--body-file") + 1])
        captured_body_contents.append(body_file_path.read_text(encoding="utf-8"))
        return _completed("https://example.com\n")

    with patch("subprocess.run", side_effect=capture_body_file_contents):
        trigger_bugbot_module.trigger_bugbot(owner="acme", repo="widget", number=42)
    assert len(captured_body_contents) == 1
    assert captured_body_contents[0] == "bugbot run\n"


def test_should_return_comment_url_from_gh_stdout() -> None:
    expected_url = "https://github.com/acme/widget/pull/42#issuecomment-12345"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(f"{expected_url}\n")
        comment_url = trigger_bugbot_module.trigger_bugbot(
            owner="acme", repo="widget", number=42
        )
    assert comment_url == expected_url


def test_should_remove_temp_body_file_after_invocation() -> None:
    captured_body_paths: list[Path] = []

    def capture_body_file_contents(*subprocess_args, **_subprocess_kwargs):
        invoked_argv = subprocess_args[0]
        captured_body_paths.append(
            Path(invoked_argv[invoked_argv.index("--body-file") + 1])
        )
        return _completed("https://example.com\n")

    with patch("subprocess.run", side_effect=capture_body_file_contents):
        trigger_bugbot_module.trigger_bugbot(owner="acme", repo="widget", number=42)
    assert len(captured_body_paths) == 1
    assert not captured_body_paths[0].exists()


def test_should_raise_when_gh_subprocess_fails() -> None:
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        with pytest.raises(subprocess.CalledProcessError):
            trigger_bugbot_module.trigger_bugbot(owner="acme", repo="widget", number=42)


def test_should_write_imported_constant_directly_without_local_alias() -> None:
    captured_body_contents: list[str] = []

    def capture_body_file_contents(*subprocess_args, **_subprocess_kwargs):
        invoked_argv = subprocess_args[0]
        body_file_path = Path(invoked_argv[invoked_argv.index("--body-file") + 1])
        captured_body_contents.append(body_file_path.read_text(encoding="utf-8"))
        return _completed("https://example.com\n")

    with patch("subprocess.run", side_effect=capture_body_file_contents):
        trigger_bugbot_module.trigger_bugbot(owner="acme", repo="widget", number=99)
    assert len(captured_body_contents) == 1
    assert (
        captured_body_contents[0]
        == trigger_bugbot_module.BUGBOT_RUN_TRIGGER_PHRASE
    )


def test_should_render_repo_arg_via_named_template_constant() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("https://example.com\n")
        trigger_bugbot_module.trigger_bugbot(owner="acme", repo="widget", number=42)
    invoked_argv = mock_run.call_args[0][0]
    expected_repo_arg = trigger_bugbot_module.GH_REPO_ARG_TEMPLATE.format(
        owner="acme", repo="widget"
    )
    assert expected_repo_arg == "acme/widget"
    repo_flag_index = invoked_argv.index("--repo")
    assert invoked_argv[repo_flag_index + 1] == expected_repo_arg
