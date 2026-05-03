"""Tests for mark_pr_ready.

Covers:
- gh pr ready is invoked with the PR number and --repo flag
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
    module_path = Path(__file__).parent / "mark_pr_ready.py"
    spec = importlib.util.spec_from_file_location("mark_pr_ready", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mark_pr_ready_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def test_should_invoke_gh_pr_ready_with_number_and_repo() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed('Pull request "#42" is marked as ready')
        mark_pr_ready_module.mark_pr_ready(owner="acme", repo="widget", number=42)
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0:3] == ["gh", "pr", "ready"]
    assert "42" in invoked_argv
    assert "--repo" in invoked_argv
    assert "acme/widget" in invoked_argv


def test_should_raise_when_gh_subprocess_fails() -> None:
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        with pytest.raises(subprocess.CalledProcessError):
            mark_pr_ready_module.mark_pr_ready(owner="acme", repo="widget", number=42)


def test_should_render_repo_arg_via_named_template_constant() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("ok\n")
        mark_pr_ready_module.mark_pr_ready(owner="acme", repo="widget", number=42)
    invoked_argv = mock_run.call_args[0][0]
    expected_repo_arg = mark_pr_ready_module.GH_REPO_ARG_TEMPLATE.format(
        owner="acme", repo="widget"
    )
    assert expected_repo_arg == "acme/widget"
    repo_flag_index = invoked_argv.index("--repo")
    assert invoked_argv[repo_flag_index + 1] == expected_repo_arg
