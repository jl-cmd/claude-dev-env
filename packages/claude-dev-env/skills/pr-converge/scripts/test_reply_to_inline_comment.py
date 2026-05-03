"""Tests for reply_to_inline_comment.

Covers:
- gh api -X POST is invoked against the inline-comments replies endpoint
- the reply body comes from a file via gh's `body=@<path>` form (per gh-body-file rule)
- the reply id from gh's JSON output is returned
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
    module_path = Path(__file__).parent / "reply_to_inline_comment.py"
    spec = importlib.util.spec_from_file_location(
        "reply_to_inline_comment", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reply_to_inline_comment_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def test_should_invoke_gh_api_post_against_replies_endpoint(tmp_path: Path) -> None:
    body_file = tmp_path / "reply.md"
    body_file.write_text("Confirmed and fixed.\n", encoding="utf-8")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(json.dumps({"id": 7777}))
        reply_to_inline_comment_module.reply_to_inline_comment(
            owner="acme",
            repo="widget",
            number=42,
            comment_id=12345,
            body_file=body_file,
        )
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0:2] == ["gh", "api"]
    assert "-X" in invoked_argv
    assert "POST" in invoked_argv
    assert "repos/acme/widget/pulls/42/comments/12345/replies" in invoked_argv


def test_should_pass_body_via_field_at_path_form(tmp_path: Path) -> None:
    body_file = tmp_path / "reply.md"
    body_file.write_text("Confirmed and fixed.\n", encoding="utf-8")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(json.dumps({"id": 7777}))
        reply_to_inline_comment_module.reply_to_inline_comment(
            owner="acme",
            repo="widget",
            number=42,
            comment_id=12345,
            body_file=body_file,
        )
    invoked_argv = mock_run.call_args[0][0]
    assert "-F" in invoked_argv
    field_value = invoked_argv[invoked_argv.index("-F") + 1]
    assert field_value.startswith("body=@")
    assert str(body_file) in field_value


def test_should_return_reply_id_from_gh_response(tmp_path: Path) -> None:
    body_file = tmp_path / "reply.md"
    body_file.write_text("Reply text\n", encoding="utf-8")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(json.dumps({"id": 7777, "body": "..."}))
        reply_id = reply_to_inline_comment_module.reply_to_inline_comment(
            owner="acme",
            repo="widget",
            number=42,
            comment_id=12345,
            body_file=body_file,
        )
    assert reply_id == 7777


def test_should_raise_when_gh_subprocess_fails(tmp_path: Path) -> None:
    body_file = tmp_path / "reply.md"
    body_file.write_text("Reply text\n", encoding="utf-8")
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        with pytest.raises(subprocess.CalledProcessError):
            reply_to_inline_comment_module.reply_to_inline_comment(
                owner="acme",
                repo="widget",
                number=42,
                comment_id=12345,
                body_file=body_file,
            )


def test_should_build_body_field_value_from_named_prefix_constant(
    tmp_path: Path,
) -> None:
    body_file = tmp_path / "reply.md"
    body_file.write_text("Reply text\n", encoding="utf-8")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(json.dumps({"id": 7777}))
        reply_to_inline_comment_module.reply_to_inline_comment(
            owner="acme",
            repo="widget",
            number=42,
            comment_id=12345,
            body_file=body_file,
        )
    invoked_argv = mock_run.call_args[0][0]
    field_value = invoked_argv[invoked_argv.index("-F") + 1]
    expected_prefix = (
        reply_to_inline_comment_module.GH_FIELD_BODY_AT_PREFIX
    )
    assert expected_prefix == "body=@"
    assert field_value == f"{expected_prefix}{body_file}"


def test_should_extract_int_id_from_mixed_typed_response_payload(
    tmp_path: Path,
) -> None:
    body_file = tmp_path / "reply.md"
    body_file.write_text("Reply text\n", encoding="utf-8")
    response_with_string_and_object_fields = json.dumps(
        {
            "id": 7777,
            "body": "Reply body text",
            "user": {"login": "octocat", "id": 1},
            "created_at": "2026-05-02T12:00:00Z",
        }
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(response_with_string_and_object_fields)
        reply_id = reply_to_inline_comment_module.reply_to_inline_comment(
            owner="acme",
            repo="widget",
            number=42,
            comment_id=12345,
            body_file=body_file,
        )
    assert reply_id == 7777
