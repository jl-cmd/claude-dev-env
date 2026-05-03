"""Tests for view_pr_context.

Covers:
- gh pr view is invoked with the documented --json field list
- the parsed JSON object is returned
- subprocess errors propagate
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def _load_module() -> ModuleType:
    module_path = Path(__file__).parent / "view_pr_context.py"
    spec = importlib.util.spec_from_file_location("view_pr_context", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


view_pr_context_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def test_should_invoke_gh_pr_view_with_documented_field_list() -> None:
    payload = json.dumps(
        {
            "number": 42,
            "url": "https://github.com/acme/widget/pull/42",
            "headRefOid": "abc123",
            "baseRefName": "main",
            "headRefName": "feat/x",
            "isDraft": True,
        }
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(payload)
        view_pr_context_module.view_pr_context()
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0:3] == ["gh", "pr", "view"]
    assert "--json" in invoked_argv
    fields_arg = invoked_argv[invoked_argv.index("--json") + 1]
    for required_field in (
        "number",
        "url",
        "headRefOid",
        "baseRefName",
        "headRefName",
        "isDraft",
    ):
        assert required_field in fields_arg


def test_should_return_parsed_json_object() -> None:
    payload = {
        "number": 42,
        "url": "https://github.com/acme/widget/pull/42",
        "headRefOid": "abc123",
        "baseRefName": "main",
        "headRefName": "feat/x",
        "isDraft": True,
    }
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(json.dumps(payload))
        pr_context = view_pr_context_module.view_pr_context()
    assert pr_context == payload


def test_should_raise_when_gh_subprocess_fails() -> None:
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        with pytest.raises(subprocess.CalledProcessError):
            view_pr_context_module.view_pr_context()


def test_should_pass_imported_constant_directly_without_local_alias() -> None:
    payload = json.dumps(
        {
            "number": 7,
            "url": "https://github.com/acme/widget/pull/7",
            "headRefOid": "deadbeef",
            "baseRefName": "main",
            "headRefName": "feat/y",
            "isDraft": False,
        }
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(payload)
        view_pr_context_module.view_pr_context()
    invoked_argv = mock_run.call_args[0][0]
    fields_arg = invoked_argv[invoked_argv.index("--json") + 1]
    expected_fields = view_pr_context_module.PR_CONTEXT_FIELDS
    assert fields_arg is expected_fields
