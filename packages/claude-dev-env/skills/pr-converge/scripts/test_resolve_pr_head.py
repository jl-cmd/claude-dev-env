"""Tests for resolve_pr_head.

Covers:
- gh command targets the single-object PR endpoint with --jq .head.sha
- single-object endpoint does NOT use --paginate or --slurp (per gh-paginate rule)
- the trimmed SHA is returned
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
    module_path = Path(__file__).parent / "resolve_pr_head.py"
    spec = importlib.util.spec_from_file_location("resolve_pr_head", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


resolve_pr_head_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def test_should_invoke_gh_against_single_object_pr_endpoint() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("85309a0789e\n")
        resolve_pr_head_module.resolve_pr_head(owner="acme", repo="widget", number=42)
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0] == "gh"
    assert invoked_argv[1] == "api"
    assert invoked_argv[2] == "repos/acme/widget/pulls/42"
    assert "--jq" in invoked_argv
    assert ".head.sha" in invoked_argv


def test_should_not_use_paginate_or_slurp_on_single_object_endpoint() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("abc\n")
        resolve_pr_head_module.resolve_pr_head(owner="acme", repo="widget", number=42)
    invoked_argv = mock_run.call_args[0][0]
    assert "--paginate" not in invoked_argv
    assert "--slurp" not in invoked_argv


def test_should_return_trimmed_sha() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("  85309a0789e  \n")
        resolved_sha = resolve_pr_head_module.resolve_pr_head(
            owner="acme", repo="widget", number=42
        )
    assert resolved_sha == "85309a0789e"


def test_should_raise_when_gh_subprocess_fails() -> None:
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        with pytest.raises(subprocess.CalledProcessError):
            resolve_pr_head_module.resolve_pr_head(
                owner="acme", repo="widget", number=42
            )
