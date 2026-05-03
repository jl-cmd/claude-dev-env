"""Tests for fetch_copilot_reviews.

Covers:
- gh command uses --paginate --slurp (per gh-paginate rule)
- per-page filter happens in Python after fetching all pages
- only copilot-pull-request-reviewer[bot] reviews are returned
- reviews are sorted newest-first by submitted_at
- reviews with state APPROVED are classified "clean"
- reviews with state CHANGES_REQUESTED or COMMENTED are classified "dirty"
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
    module_path = Path(__file__).parent / "fetch_copilot_reviews.py"
    spec = importlib.util.spec_from_file_location("fetch_copilot_reviews", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch_copilot_reviews_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def test_should_invoke_gh_with_paginate_slurp_against_reviews_endpoint() -> None:
    pages_payload = json.dumps([[]])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        fetch_copilot_reviews_module.fetch_copilot_reviews(
            owner="acme", repo="widget", number=42
        )
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0] == "gh"
    assert invoked_argv[1] == "api"
    assert "repos/acme/widget/pulls/42/reviews?per_page=100" in invoked_argv[2]
    assert "--paginate" in invoked_argv
    assert "--slurp" in invoked_argv


def test_should_filter_to_copilot_reviewer_only() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "cursor[bot]"},
                    "state": "COMMENTED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "bugbot stuff",
                },
                {
                    "id": 2,
                    "user": {"login": "copilot-pull-request-reviewer[bot]"},
                    "state": "CHANGES_REQUESTED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-02T00:00:00Z",
                    "body": "copilot finding",
                },
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_copilot_reviews_module.fetch_copilot_reviews(
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
                    "user": {"login": "copilot-pull-request-reviewer[bot]"},
                    "state": "APPROVED",
                    "commit_id": "old",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "lgtm",
                }
            ],
            [
                {
                    "id": 11,
                    "user": {"login": "copilot-pull-request-reviewer[bot]"},
                    "state": "CHANGES_REQUESTED",
                    "commit_id": "new",
                    "submitted_at": "2026-01-03T00:00:00Z",
                    "body": "issues found",
                },
                {
                    "id": 12,
                    "user": {"login": "copilot-pull-request-reviewer[bot]"},
                    "state": "APPROVED",
                    "commit_id": "mid",
                    "submitted_at": "2026-01-02T00:00:00Z",
                    "body": "lgtm",
                },
            ],
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_copilot_reviews_module.fetch_copilot_reviews(
            owner="acme", repo="widget", number=42
        )
    submitted_at_sequence = [each_review["submitted_at"] for each_review in all_reviews]
    assert submitted_at_sequence == [
        "2026-01-03T00:00:00Z",
        "2026-01-02T00:00:00Z",
        "2026-01-01T00:00:00Z",
    ]


def test_should_classify_dirty_review_when_state_is_changes_requested() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "copilot-pull-request-reviewer[bot]"},
                    "state": "CHANGES_REQUESTED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "Issues need addressing.",
                }
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_copilot_reviews_module.fetch_copilot_reviews(
            owner="acme", repo="widget", number=42
        )
    assert all_reviews[0]["classification"] == "dirty"


def test_should_classify_dirty_review_when_state_is_commented_with_body() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "copilot-pull-request-reviewer[bot]"},
                    "state": "COMMENTED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "Found a couple of nits inline.",
                }
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_copilot_reviews_module.fetch_copilot_reviews(
            owner="acme", repo="widget", number=42
        )
    assert all_reviews[0]["classification"] == "dirty"


def test_should_classify_clean_review_when_state_is_commented_with_empty_body() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "copilot-pull-request-reviewer[bot]"},
                    "state": "COMMENTED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "",
                }
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_copilot_reviews_module.fetch_copilot_reviews(
            owner="acme", repo="widget", number=42
        )
    assert all_reviews[0]["classification"] == "clean"


def test_should_dispatch_dirty_classification_off_copilot_dirty_review_states_tuple() -> None:
    source_text = (
        Path(__file__).resolve().parent / "fetch_copilot_reviews.py"
    ).read_text(encoding="utf-8")
    assert "ALL_COPILOT_DIRTY_REVIEW_STATES" in source_text
    assert "in ALL_COPILOT_DIRTY_REVIEW_STATES" in source_text


def test_should_classify_clean_review_when_state_is_approved() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "copilot-pull-request-reviewer[bot]"},
                    "state": "APPROVED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "looks good",
                }
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_copilot_reviews_module.fetch_copilot_reviews(
            owner="acme", repo="widget", number=42
        )
    assert all_reviews[0]["classification"] == "clean"


def test_should_reference_copilot_login_constant_directly_without_local_alias() -> None:
    source_text = (
        Path(__file__).resolve().parent / "fetch_copilot_reviews.py"
    ).read_text(encoding="utf-8")
    assert "copilot_reviewer_login = COPILOT_REVIEWER_LOGIN" not in source_text
    assert "COPILOT_REVIEWER_LOGIN" in source_text


def test_should_raise_when_gh_subprocess_fails() -> None:
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        with pytest.raises(subprocess.CalledProcessError):
            fetch_copilot_reviews_module.fetch_copilot_reviews(
                owner="acme", repo="widget", number=42
            )


def test_should_return_entries_whose_keys_are_strings() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "copilot-pull-request-reviewer[bot]"},
                    "state": "APPROVED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "looks good",
                }
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = fetch_copilot_reviews_module.fetch_copilot_reviews(
            owner="acme", repo="widget", number=42
        )
    assert len(all_reviews) == 1
    first_review_entry = all_reviews[0]
    assert isinstance(first_review_entry, dict)
    assert all(isinstance(each_key, str) for each_key in first_review_entry.keys())
