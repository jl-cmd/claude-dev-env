"""Behavioral tests for the review and Bugbot convergence gate leaves.

::

    _flatten_paginated_reviews(two pages) -> newest-first flat list
    _bugbot_run_conclusion_detail(success) -> (True, "check run ...")
    _check_bugbot(named complete run) -> (True, "check run ...")

Each test drives the real leaf, stubbing only the ``gh`` transport helpers.
"""

from __future__ import annotations

import json

import pytest

import check_convergence_gates as gates


def test_flatten_paginated_reviews_flattens_and_sorts_newest_first() -> None:
    pages = [
        [{"id": 1, "submitted_at": "2026-01-01T00:00:00Z"}],
        [{"id": 2, "submitted_at": "2026-03-01T00:00:00Z"}],
    ]
    flattened = gates._flatten_paginated_reviews(json.dumps(pages))
    assert flattened is not None
    assert [each_review["id"] for each_review in flattened] == [2, 1]


def test_flatten_paginated_reviews_returns_none_for_non_list_payload() -> None:
    assert (
        gates._flatten_paginated_reviews(json.dumps({"message": "Not Found"})) is None
    )


def test_bugbot_run_conclusion_detail_passes_on_a_complete_conclusion() -> None:
    complete_conclusion = gates.ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS[0]
    passed, detail = gates._bugbot_run_conclusion_detail(
        {"id": 55, "conclusion": complete_conclusion, "html_url": ""}
    )
    assert passed is True
    assert "check run 55" in detail


def test_check_bugbot_reports_success_when_the_named_run_is_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    complete_conclusion = gates.ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS[0]
    run_name = f"x {gates.BUGBOT_CHECK_RUN_NAME_SUBSTRING} y"
    payload = {
        "check_runs": [
            {
                "name": run_name,
                "id": 9,
                "conclusion": complete_conclusion,
                "html_url": "",
            }
        ]
    }

    def _stub_gh_api(endpoint_path: str) -> tuple[int, str]:
        return 0, json.dumps(payload)

    monkeypatch.setattr(gates, "_gh_api", _stub_gh_api)
    passed, detail = gates._check_bugbot(owner="o", repo="r", sha="abc")
    assert passed is True
    assert "check run 9" in detail


def should_evaluate_mergeable_from_pr_object_clean() -> None:
    passed, detail = gates._evaluate_mergeable_from_pr_object(
        {"mergeable": True, "mergeable_state": "clean"}
    )
    assert passed is True
    assert detail == "clean"


def should_evaluate_mergeable_from_pr_object_unknown() -> None:
    passed, detail = gates._evaluate_mergeable_from_pr_object(
        {"mergeable": None, "mergeable_state": "unknown"}
    )
    assert passed is False
    assert detail == "unknown"
