"""Tests for reviewer_fetch_core.

Covers:
- fetch_reviewer_reviews invokes gh against the reviews endpoint with --paginate --slurp
- login filter applies case-insensitively as a substring on user.login
- entries missing submitted_at or id are filtered out
- reviews are sorted newest-first by submitted_at
- the spec.classify_review callable is invoked for each surviving review
- subprocess errors propagate
- fetch_reviewer_inline_comments returns empty when no review for current_head
- fetch_reviewer_inline_comments only returns comments anchored to the latest review
- fetch_reviewer_inline_comments invokes gh against the comments endpoint with --paginate --slurp
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch


def _load_module() -> ModuleType:
    module_path = Path(__file__).parent / "reviewer_fetch_core.py"
    spec = importlib.util.spec_from_file_location("reviewer_fetch_core", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reviewer_fetch_core_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def _fake_spec(*, login_filter_substring: str = "test") -> object:
    fake_spec_object = MagicMock()
    fake_spec_object.login_filter_substring = login_filter_substring
    fake_spec_object.classify_review = MagicMock(return_value="clean")
    return fake_spec_object


def test_fetch_reviewer_reviews_invokes_gh_with_paginate_slurp_against_reviews_endpoint() -> (
    None
):
    pages_payload = json.dumps([[]])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        reviewer_fetch_core_module.fetch_reviewer_reviews(
            _fake_spec(), owner="acme", repo="widget", number=42
        )
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0] == "gh"
    assert invoked_argv[1] == "api"
    assert "repos/acme/widget/pulls/42/reviews?per_page=100" in invoked_argv[2]
    assert "--paginate" in invoked_argv
    assert "--slurp" in invoked_argv


def test_fetch_reviewer_reviews_filters_by_login_filter_substring_case_insensitively() -> (
    None
):
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "TestBot[bot]"},
                    "state": "APPROVED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "uppercase login",
                },
                {
                    "id": 2,
                    "user": {"login": "other-reviewer"},
                    "state": "APPROVED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-02T00:00:00Z",
                    "body": "no match",
                },
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = reviewer_fetch_core_module.fetch_reviewer_reviews(
            _fake_spec(login_filter_substring="test"),
            owner="acme",
            repo="widget",
            number=42,
        )
    assert len(all_reviews) == 1
    assert all_reviews[0]["review_id"] == 1


def test_fetch_reviewer_reviews_drops_entries_missing_submitted_at() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "test[bot]"},
                    "state": "APPROVED",
                    "commit_id": "abc",
                    "body": "no submitted_at",
                },
                {
                    "id": 2,
                    "user": {"login": "test[bot]"},
                    "state": "APPROVED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-02T00:00:00Z",
                    "body": "valid",
                },
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = reviewer_fetch_core_module.fetch_reviewer_reviews(
            _fake_spec(), owner="acme", repo="widget", number=42
        )
    assert [each_review["review_id"] for each_review in all_reviews] == [2]


def test_fetch_reviewer_reviews_drops_entries_missing_id() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "user": {"login": "test[bot]"},
                    "state": "APPROVED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "no id",
                },
                {
                    "id": 99,
                    "user": {"login": "test[bot]"},
                    "state": "APPROVED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-02T00:00:00Z",
                    "body": "valid",
                },
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = reviewer_fetch_core_module.fetch_reviewer_reviews(
            _fake_spec(), owner="acme", repo="widget", number=42
        )
    assert [each_review["review_id"] for each_review in all_reviews] == [99]


def test_fetch_reviewer_reviews_sorts_newest_first_across_pages() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 10,
                    "user": {"login": "test[bot]"},
                    "state": "APPROVED",
                    "commit_id": "old",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "oldest",
                }
            ],
            [
                {
                    "id": 11,
                    "user": {"login": "test[bot]"},
                    "state": "CHANGES_REQUESTED",
                    "commit_id": "new",
                    "submitted_at": "2026-01-03T00:00:00Z",
                    "body": "newest",
                },
                {
                    "id": 12,
                    "user": {"login": "test[bot]"},
                    "state": "APPROVED",
                    "commit_id": "mid",
                    "submitted_at": "2026-01-02T00:00:00Z",
                    "body": "middle",
                },
            ],
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = reviewer_fetch_core_module.fetch_reviewer_reviews(
            _fake_spec(), owner="acme", repo="widget", number=42
        )
    assert [each_review["submitted_at"] for each_review in all_reviews] == [
        "2026-01-03T00:00:00Z",
        "2026-01-02T00:00:00Z",
        "2026-01-01T00:00:00Z",
    ]


def test_fetch_reviewer_reviews_invokes_classify_callable_per_review() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "test[bot]"},
                    "state": "APPROVED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "body": "first",
                },
                {
                    "id": 2,
                    "user": {"login": "test[bot]"},
                    "state": "CHANGES_REQUESTED",
                    "commit_id": "abc",
                    "submitted_at": "2026-01-02T00:00:00Z",
                    "body": "second",
                },
            ]
        ]
    )
    classify_callable = MagicMock(side_effect=["dirty", "clean"])
    fake_spec_object = MagicMock()
    fake_spec_object.login_filter_substring = "test"
    fake_spec_object.classify_review = classify_callable
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_reviews = reviewer_fetch_core_module.fetch_reviewer_reviews(
            fake_spec_object, owner="acme", repo="widget", number=42
        )
    assert classify_callable.call_count == 2
    assert {each_review["classification"] for each_review in all_reviews} == {
        "dirty",
        "clean",
    }


def test_fetch_reviewer_reviews_propagates_subprocess_errors() -> None:
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        try:
            reviewer_fetch_core_module.fetch_reviewer_reviews(
                _fake_spec(), owner="acme", repo="widget", number=42
            )
            assert False, "expected CalledProcessError"
        except subprocess.CalledProcessError:
            pass


def test_fetch_reviewer_inline_comments_returns_empty_when_no_review_for_head() -> None:
    no_matching_review = [
        {
            "review_id": 1,
            "commit_id": "other_sha",
            "submitted_at": "2026-01-01T00:00:00Z",
            "state": "APPROVED",
            "body": "",
            "classification": "clean",
        }
    ]
    with patch("subprocess.run") as mock_run:
        all_inline_comments = reviewer_fetch_core_module.fetch_reviewer_inline_comments(
            _fake_spec(),
            owner="acme",
            repo="widget",
            number=42,
            current_head="missing_sha",
            all_reviews=no_matching_review,
        )
    assert all_inline_comments == []
    mock_run.assert_not_called()


def test_fetch_reviewer_inline_comments_invokes_gh_against_comments_endpoint() -> None:
    pages_payload = json.dumps([[]])
    matching_review = [
        {
            "review_id": 1,
            "commit_id": "abc123",
            "submitted_at": "2026-01-01T00:00:00Z",
            "state": "APPROVED",
            "body": "",
            "classification": "clean",
        }
    ]
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        reviewer_fetch_core_module.fetch_reviewer_inline_comments(
            _fake_spec(),
            owner="acme",
            repo="widget",
            number=42,
            current_head="abc123",
            all_reviews=matching_review,
        )
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0] == "gh"
    assert invoked_argv[1] == "api"
    assert "repos/acme/widget/pulls/42/comments?per_page=100" in invoked_argv[2]
    assert "--paginate" in invoked_argv
    assert "--slurp" in invoked_argv


def test_fetch_reviewer_inline_comments_anchors_to_latest_review_id_for_head() -> None:
    reviews_newest_first = [
        {
            "review_id": 11,
            "commit_id": "same_sha",
            "submitted_at": "2026-01-02T00:00:00Z",
            "state": "APPROVED",
            "body": "lgtm",
            "classification": "clean",
        },
        {
            "review_id": 10,
            "commit_id": "same_sha",
            "submitted_at": "2026-01-01T00:00:00Z",
            "state": "CHANGES_REQUESTED",
            "body": "fix",
            "classification": "dirty",
        },
    ]
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 100,
                    "user": {"login": "test[bot]"},
                    "commit_id": "same_sha",
                    "pull_request_review_id": 10,
                    "body": "stale",
                    "path": "x.py",
                    "line": 1,
                },
                {
                    "id": 101,
                    "user": {"login": "test[bot]"},
                    "commit_id": "same_sha",
                    "pull_request_review_id": 11,
                    "body": "current",
                    "path": "x.py",
                    "line": 2,
                },
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_inline_comments = reviewer_fetch_core_module.fetch_reviewer_inline_comments(
            _fake_spec(),
            owner="acme",
            repo="widget",
            number=42,
            current_head="same_sha",
            all_reviews=reviews_newest_first,
        )
    assert [each_comment["comment_id"] for each_comment in all_inline_comments] == [101]


def test_fetch_reviewer_inline_comments_filters_login_substring() -> None:
    matching_review = [
        {
            "review_id": 9,
            "commit_id": "abc",
            "submitted_at": "2026-01-01T00:00:00Z",
            "state": "APPROVED",
            "body": "",
            "classification": "clean",
        }
    ]
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "test[bot]"},
                    "commit_id": "abc",
                    "pull_request_review_id": 9,
                    "body": "match",
                    "path": "f.py",
                    "line": 1,
                },
                {
                    "id": 2,
                    "user": {"login": "other-reviewer"},
                    "commit_id": "abc",
                    "pull_request_review_id": 9,
                    "body": "no match",
                    "path": "f.py",
                    "line": 2,
                },
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_inline_comments = reviewer_fetch_core_module.fetch_reviewer_inline_comments(
            _fake_spec(login_filter_substring="test"),
            owner="acme",
            repo="widget",
            number=42,
            current_head="abc",
            all_reviews=matching_review,
        )
    assert [each_comment["comment_id"] for each_comment in all_inline_comments] == [1]


def test_fetch_reviewer_inline_comments_propagates_subprocess_errors() -> None:
    matching_review = [
        {
            "review_id": 1,
            "commit_id": "abc",
            "submitted_at": "2026-01-01T00:00:00Z",
            "state": "APPROVED",
            "body": "",
            "classification": "clean",
        }
    ]
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        try:
            reviewer_fetch_core_module.fetch_reviewer_inline_comments(
                _fake_spec(),
                owner="acme",
                repo="widget",
                number=42,
                current_head="abc",
                all_reviews=matching_review,
            )
            assert False, "expected CalledProcessError"
        except subprocess.CalledProcessError:
            pass
