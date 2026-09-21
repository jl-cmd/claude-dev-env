"""Tests for the agent merge-readiness check."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

import agent_merge_check
from dev_env_scripts_constants.agent_merge_check_constants import (
    BEHIND_HOLD_REASON,
    BLOCKED_HOLD_REASON,
    DIRTY_HOLD_REASON,
    DRAFT_HOLD_REASON,
    HOLD_VERDICT_LABEL,
    MERGE_VERDICT_LABEL,
    SETTLE_ATTEMPT_COUNT,
    UNSTABLE_HOLD_REASON,
)

CLEAN_PULL_REQUEST = {
    "number": 1442,
    "draft": False,
    "mergeable_state": "clean",
    "head": {"sha": "ab845eb6945650055ebe852312a9057b9f067d6a"},
}


def _pull_request(**all_overrides: object) -> dict[str, object]:
    return {**CLEAN_PULL_REQUEST, **all_overrides}


def test_clean_pull_request_with_no_open_thread_may_merge() -> None:
    assert agent_merge_check.hold_reason(CLEAN_PULL_REQUEST, 0) is None


@pytest.mark.parametrize(
    ("all_overrides", "expected_reason"),
    [
        ({"draft": True}, DRAFT_HOLD_REASON),
        ({"mergeable_state": "behind"}, BEHIND_HOLD_REASON),
        ({"mergeable_state": "dirty"}, DIRTY_HOLD_REASON),
        ({"mergeable_state": "blocked"}, BLOCKED_HOLD_REASON),
        ({"mergeable_state": "unstable"}, UNSTABLE_HOLD_REASON),
    ],
)
def test_each_unready_state_holds_with_its_own_reason(
    all_overrides: dict[str, object],
    expected_reason: str,
) -> None:
    assert (
        agent_merge_check.hold_reason(_pull_request(**all_overrides), 0)
        == expected_reason
    )


def test_a_draft_holds_even_when_its_merge_state_is_clean() -> None:
    assert (
        agent_merge_check.hold_reason(_pull_request(draft=True), 0) == DRAFT_HOLD_REASON
    )


def test_an_unreported_merge_state_holds_and_names_what_github_said() -> None:
    reason = agent_merge_check.hold_reason(_pull_request(mergeable_state="unknown"), 0)
    assert reason is not None
    assert "unknown" in reason


def test_an_open_review_thread_holds_a_green_pull_request() -> None:
    reason = agent_merge_check.hold_reason(CLEAN_PULL_REQUEST, 2)
    assert reason is not None
    assert "2" in reason


def test_an_open_thread_count_reaches_the_verdict_line() -> None:
    reason = agent_merge_check.hold_reason(CLEAN_PULL_REQUEST, 1)
    line = agent_merge_check.verdict_line(
        "jl-cmd/claude-dev-env", CLEAN_PULL_REQUEST, reason
    )
    assert line.startswith(HOLD_VERDICT_LABEL)
    assert "jl-cmd/claude-dev-env#1442" in line


def test_the_ready_verdict_line_names_the_repository_and_head() -> None:
    line = agent_merge_check.verdict_line(
        "jl-cmd/claude-dev-env", CLEAN_PULL_REQUEST, None
    )
    assert line.startswith(MERGE_VERDICT_LABEL)
    assert "jl-cmd/claude-dev-env#1442" in line
    assert "ab845eb" in line


def test_a_resolved_thread_and_an_outdated_thread_hold_nothing_back() -> None:
    all_thread_records = [
        {"isResolved": True, "isOutdated": False},
        {"isResolved": False, "isOutdated": True},
    ]
    assert agent_merge_check.count_unresolved_threads(all_thread_records) == 0


def test_an_unresolved_current_thread_counts() -> None:
    all_thread_records = [
        {"isResolved": False, "isOutdated": False},
        {"isResolved": True, "isOutdated": False},
        {"isResolved": False, "isOutdated": False},
    ]
    assert agent_merge_check.count_unresolved_threads(all_thread_records) == 2


def test_a_thread_record_of_another_shape_counts_as_nothing() -> None:
    assert agent_merge_check.count_unresolved_threads(["", None]) == 0


def test_read_pull_request_returns_the_fields_the_api_answered_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_merge_check,
        "_request_json",
        lambda url, token, all_payload_fields: CLEAN_PULL_REQUEST,
    )
    assert (
        agent_merge_check.read_pull_request("jl-cmd/claude-dev-env", 1442, "token")
        == CLEAN_PULL_REQUEST
    )


def test_read_pull_request_rejects_an_answer_of_another_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_merge_check,
        "_request_json",
        lambda url, token, all_payload_fields: ["not a pull request"],
    )
    with pytest.raises(agent_merge_check.MergeCheckError):
        agent_merge_check.read_pull_request("jl-cmd/claude-dev-env", 1442, "token")


def test_read_unresolved_thread_count_reads_the_rest_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_merge_check,
        "_request_json",
        lambda url, token, all_payload_fields: [
            {"isResolved": False, "isOutdated": False},
            {"isResolved": True, "isOutdated": False},
        ],
    )
    assert (
        agent_merge_check.read_unresolved_thread_count(
            "jl-cmd/claude-dev-env", 1442, "token"
        )
        == 1
    )


def test_read_unresolved_thread_count_falls_back_to_the_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _answer(
        url: str,
        token: str,
        all_payload_fields: object,
    ) -> object:
        if all_payload_fields is None:
            raise agent_merge_check.MergeCheckError("HTTP Error 403: Forbidden")
        return {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [{"isResolved": False, "isOutdated": False}]
                        }
                    }
                }
            }
        }

    monkeypatch.setattr(agent_merge_check, "_request_json", _answer)
    assert (
        agent_merge_check.read_unresolved_thread_count(
            "jl-cmd/claude-dev-env", 1442, "token"
        )
        == 1
    )


def test_read_unresolved_thread_count_rejects_a_query_answer_of_another_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _answer(
        url: str,
        token: str,
        all_payload_fields: object,
    ) -> object:
        if all_payload_fields is None:
            raise agent_merge_check.MergeCheckError("HTTP Error 403: Forbidden")
        return {"errors": [{"message": "Bad credentials"}]}

    monkeypatch.setattr(agent_merge_check, "_request_json", _answer)
    with pytest.raises(agent_merge_check.MergeCheckError):
        agent_merge_check.read_unresolved_thread_count(
            "jl-cmd/claude-dev-env", 1442, "token"
        )


def test_read_settled_pull_request_reads_again_while_the_state_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_answers = [
        _pull_request(mergeable_state="unknown"),
        _pull_request(mergeable_state="unknown"),
        CLEAN_PULL_REQUEST,
    ]
    all_waits: list[float] = []
    monkeypatch.setattr(
        agent_merge_check,
        "read_pull_request",
        lambda slug, number, token: all_answers.pop(0),
    )
    settled = agent_merge_check.read_settled_pull_request(
        "jl-cmd/claude-dev-env", 1442, "token", all_waits.append
    )
    assert settled == CLEAN_PULL_REQUEST
    assert len(all_waits) == 2


def test_read_settled_pull_request_stops_after_its_last_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_waits: list[float] = []
    read_count = 0

    def _unknown(slug: str, number: int, token: str) -> dict[str, object]:
        nonlocal read_count
        read_count += 1
        return _pull_request(mergeable_state="unknown")

    monkeypatch.setattr(agent_merge_check, "read_pull_request", _unknown)
    settled = agent_merge_check.read_settled_pull_request(
        "jl-cmd/claude-dev-env", 1442, "token", all_waits.append
    )
    assert settled["mergeable_state"] == "unknown"
    assert read_count == SETTLE_ATTEMPT_COUNT
    assert len(all_waits) == SETTLE_ATTEMPT_COUNT - 1


def test_read_settled_pull_request_waits_for_no_settled_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_waits: list[float] = []
    monkeypatch.setattr(
        agent_merge_check,
        "read_pull_request",
        lambda slug, number, token: CLEAN_PULL_REQUEST,
    )
    agent_merge_check.read_settled_pull_request(
        "jl-cmd/claude-dev-env", 1442, "token", all_waits.append
    )
    assert all_waits == []


def test_a_missing_token_reports_the_error_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert agent_merge_check.main(["jl-cmd/claude-dev-env", "1442"]) == 2


def test_a_ready_pull_request_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "token")
    monkeypatch.setattr(
        agent_merge_check,
        "read_pull_request",
        lambda slug, number, token: CLEAN_PULL_REQUEST,
    )
    monkeypatch.setattr(agent_merge_check.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        agent_merge_check,
        "read_unresolved_thread_count",
        lambda slug, number, token: 0,
    )
    assert agent_merge_check.main(["jl-cmd/claude-dev-env", "1442"]) == 0


def test_a_held_pull_request_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "token")
    monkeypatch.setattr(
        agent_merge_check,
        "read_pull_request",
        lambda slug, number, token: _pull_request(mergeable_state="behind"),
    )
    monkeypatch.setattr(
        agent_merge_check,
        "read_unresolved_thread_count",
        lambda slug, number, token: 0,
    )
    assert agent_merge_check.main(["jl-cmd/claude-dev-env", "1442"]) == 1


def test_an_unreadable_pull_request_exits_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail(slug: str, number: int, token: str) -> dict[str, object]:
        raise agent_merge_check.MergeCheckError("no route to host")

    monkeypatch.setenv("GH_TOKEN", "token")
    monkeypatch.setattr(agent_merge_check, "read_pull_request", _fail)
    assert agent_merge_check.main(["jl-cmd/claude-dev-env", "1442"]) == 2
