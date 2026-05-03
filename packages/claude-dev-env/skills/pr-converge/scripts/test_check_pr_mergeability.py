"""Tests for check_pr_mergeability.

Covers:
- gh pr view is invoked with the documented mergeability --json field list
- the parsed JSON object is returned with mergeable/mergeStateStatus/headRefOid keys
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
    module_path = Path(__file__).parent / "check_pr_mergeability.py"
    spec = importlib.util.spec_from_file_location("check_pr_mergeability", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_pr_mergeability_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def test_should_invoke_gh_pr_view_with_mergeability_field_list() -> None:
    payload = json.dumps(
        {
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
            "headRefOid": "abc123",
        }
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(payload)
        check_pr_mergeability_module.check_pr_mergeability(
            owner="acme", repo="widget", number=42
        )
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0:3] == ["gh", "pr", "view"]
    assert "--json" in invoked_argv
    fields_arg = invoked_argv[invoked_argv.index("--json") + 1]
    for required_field in ("mergeable", "mergeStateStatus", "headRefOid"):
        assert required_field in fields_arg


def test_should_pass_pr_number_and_repo_arg_for_explicit_targeting() -> None:
    payload = json.dumps(
        {
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
            "headRefOid": "abc123",
        }
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(payload)
        check_pr_mergeability_module.check_pr_mergeability(
            owner="acme", repo="widget", number=42
        )
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[3] == "42"
    assert "--repo" in invoked_argv
    repo_arg_value = invoked_argv[invoked_argv.index("--repo") + 1]
    assert repo_arg_value == "acme/widget"


def test_should_return_parsed_json_object_with_mergeability_keys() -> None:
    payload = {
        "mergeable": "CONFLICTING",
        "mergeStateStatus": "DIRTY",
        "headRefOid": "deadbeef",
    }
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(json.dumps(payload))
        mergeability_state = check_pr_mergeability_module.check_pr_mergeability(
            owner="acme", repo="widget", number=42
        )
    assert mergeability_state == payload
    assert mergeability_state["mergeable"] == "CONFLICTING"
    assert mergeability_state["mergeStateStatus"] == "DIRTY"
    assert mergeability_state["headRefOid"] == "deadbeef"


def test_should_raise_when_gh_subprocess_fails() -> None:
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        with pytest.raises(subprocess.CalledProcessError):
            check_pr_mergeability_module.check_pr_mergeability(
                owner="acme", repo="widget", number=42
            )


def test_should_pass_imported_constant_directly_without_local_alias() -> None:
    payload = json.dumps(
        {
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
            "headRefOid": "abc",
        }
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(payload)
        check_pr_mergeability_module.check_pr_mergeability(
            owner="acme", repo="widget", number=42
        )
    invoked_argv = mock_run.call_args[0][0]
    fields_arg = invoked_argv[invoked_argv.index("--json") + 1]
    expected_fields = check_pr_mergeability_module.MERGEABILITY_FIELDS
    assert fields_arg is expected_fields
