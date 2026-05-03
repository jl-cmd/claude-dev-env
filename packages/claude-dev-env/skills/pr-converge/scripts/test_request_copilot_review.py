"""Tests for request_copilot_review.

Covers:
- gh api -X POST is invoked against requested_reviewers endpoint
- the reviewer id literal is `copilot-pull-request-reviewer[bot]` (the [bot]
  suffix is load-bearing per skills/copilot-review/SKILL.md)
- subprocess errors propagate
- the field carries the documented `reviewers[]=<id>` form
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def _load_module() -> ModuleType:
    module_path = Path(__file__).parent / "request_copilot_review.py"
    spec = importlib.util.spec_from_file_location("request_copilot_review", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


request_copilot_review_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def test_should_invoke_gh_api_post_against_requested_reviewers_endpoint() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("{}")
        request_copilot_review_module.request_copilot_review(
            owner="acme", repo="widget", number=42
        )
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0:2] == ["gh", "api"]
    assert "-X" in invoked_argv
    assert "POST" in invoked_argv
    assert "repos/acme/widget/pulls/42/requested_reviewers" in invoked_argv


def test_should_request_copilot_with_bot_suffix_literal() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("{}")
        request_copilot_review_module.request_copilot_review(
            owner="acme", repo="widget", number=42
        )
    invoked_argv = mock_run.call_args[0][0]
    assert "reviewers[]=copilot-pull-request-reviewer[bot]" in invoked_argv


def test_should_pass_reviewer_field_via_dash_f_flag() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("{}")
        request_copilot_review_module.request_copilot_review(
            owner="acme", repo="widget", number=42
        )
    invoked_argv = mock_run.call_args[0][0]
    assert "-f" in invoked_argv
    field_index = invoked_argv.index("-f")
    field_value = invoked_argv[field_index + 1]
    assert field_value == "reviewers[]=copilot-pull-request-reviewer[bot]"


def test_should_raise_when_gh_subprocess_fails() -> None:
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        with pytest.raises(subprocess.CalledProcessError):
            request_copilot_review_module.request_copilot_review(
                owner="acme", repo="widget", number=42
            )


def test_should_render_endpoint_via_named_template_constant() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("{}")
        request_copilot_review_module.request_copilot_review(
            owner="acme", repo="widget", number=42
        )
    invoked_argv = mock_run.call_args[0][0]
    expected_endpoint = (
        request_copilot_review_module.GH_REQUESTED_REVIEWERS_PATH_TEMPLATE.format(
            owner="acme", repo="widget", number=42
        )
    )
    assert expected_endpoint in invoked_argv
