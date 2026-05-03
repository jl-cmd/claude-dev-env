"""Tests for fetch_bugbot_reviews.

Covers:
- gh command uses --paginate --slurp (per gh-paginate rule)
- per-page filter happens in Python after fetching all pages
- only cursor[bot] reviews are returned
- reviews are sorted newest-first by submitted_at
- review bodies matching the bugbot dirty-pattern are classified "dirty"
- review bodies without the pattern are classified "clean"
- subprocess errors propagate with stderr context
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
    module_path = Path(__file__).parent / "fetch_bugbot_reviews.py"
    spec = importlib.util.spec_from_file_location("fetch_bugbot_reviews", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch_bugbot_reviews_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def test_should_invoke_gh_with_paginate_slurp_against_reviews_endpoint() -> None:
    pages_payload = json.dumps([[]])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        fetch_bugbot_reviews_module.fetch_bugbot_reviews(
            owner="acme", repo="widget", number=42
        )
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0] == "gh"
    assert invoked_argv[1] == "api"
    assert "repos/acme/widget/pulls/42/reviews?per_page=100" in invoked_argv[2]
    assert "--paginate" in invoked_argv
    assert "--slurp" in invoked_argv


def test_should_filter_to_cursor_bot_only() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "copilot-pull-request-reviewer[bot]"},
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "copilot stuff",
                },
                {
                    "id": 2,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "abc",
                    "submitted_at": "2026-01-02T00:00:00Z",
                    "body": "Cursor Bugbot has reviewed your changes and found 1 potential issue.",
                },
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_bugbot_reviews_module.fetch_bugbot_reviews(
            owner="acme", repo="widget", number=42
        )
    assert len(all_reviews) == 1
    assert all_reviews[0]["review_id"] == 2


def test_should_return_reviews_newest_first_across_pages() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 10,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "old",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "Bugbot reviewed your changes and found no new issues!",
                }
            ],
            [
                {
                    "id": 11,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "new",
                    "submitted_at": "2026-01-03T00:00:00Z",
                    "body": "Cursor Bugbot has reviewed your changes and found 2 potential issues.",
                },
                {
                    "id": 12,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "mid",
                    "submitted_at": "2026-01-02T00:00:00Z",
                    "body": "Bugbot reviewed your changes and found no new issues!",
                },
            ],
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_bugbot_reviews_module.fetch_bugbot_reviews(
            owner="acme", repo="widget", number=42
        )
    submitted_at_sequence = [each_review["submitted_at"] for each_review in all_reviews]
    assert submitted_at_sequence == [
        "2026-01-03T00:00:00Z",
        "2026-01-02T00:00:00Z",
        "2026-01-01T00:00:00Z",
    ]


def test_should_classify_dirty_review_when_body_matches_bugbot_findings_pattern() -> (
    None
):
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "Cursor Bugbot has reviewed your changes and found 3 potential issues.",
                }
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_bugbot_reviews_module.fetch_bugbot_reviews(
            owner="acme", repo="widget", number=42
        )
    assert all_reviews[0]["classification"] == "dirty"


def test_should_classify_clean_review_when_body_lacks_findings_pattern() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "Bugbot reviewed your changes and found no new issues!",
                }
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_bugbot_reviews_module.fetch_bugbot_reviews(
            owner="acme", repo="widget", number=42
        )
    assert all_reviews[0]["classification"] == "clean"


def test_should_reference_cursor_bot_login_constant_directly_without_local_alias() -> None:
    source_text = (
        Path(__file__).resolve().parent / "fetch_bugbot_reviews.py"
    ).read_text(encoding="utf-8")
    assert "cursor_bot_login = CURSOR_BOT_LOGIN" not in source_text
    assert "CURSOR_BOT_LOGIN" in source_text


def test_should_raise_when_gh_subprocess_fails() -> None:
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        with pytest.raises(subprocess.CalledProcessError):
            fetch_bugbot_reviews_module.fetch_bugbot_reviews(
                owner="acme", repo="widget", number=42
            )


def test_should_return_entries_whose_keys_are_strings() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "Bugbot reviewed your changes and found no new issues!",
                }
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_bugbot_reviews_module.fetch_bugbot_reviews(
            owner="acme", repo="widget", number=42
        )
    assert len(all_reviews) == 1
    first_review_entry = all_reviews[0]
    assert isinstance(first_review_entry, dict)
    assert all(isinstance(each_key, str) for each_key in first_review_entry.keys())
