from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import review_closure_github as reader
from dev_env_scripts_constants.review_closure_constants import APPROVALS_CHECK_NAME
from pr_verification.github_parsing import GitHubError

TOKEN = os.environ.get("REVIEW_CLOSURE_TEST_TOKEN", "test-value")


class FakeReply:
    def __init__(self, status: int, document: object) -> None:
        self.status = status
        self._body = json.dumps(document).encode("utf-8")

    def read(self) -> bytes:
        return self._body


def answer_with(
    monkeypatch: pytest.MonkeyPatch,
    all_answers_by_url_fragment: dict[str, tuple[int, object]],
) -> list[str]:
    all_requested_urls: list[str] = []

    @contextmanager
    def fake_urlopen(request: object, timeout: int = 0) -> Iterator[FakeReply]:
        url = request.full_url
        all_requested_urls.append(url)
        for each_fragment, (status, document) in all_answers_by_url_fragment.items():
            if each_fragment in url:
                yield FakeReply(status, document)
                return
        raise AssertionError(url)

    monkeypatch.setattr(reader.urllib.request, "urlopen", fake_urlopen)
    return all_requested_urls


def should_read_a_token_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)

    assert reader.github_token() == TOKEN


def should_report_a_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    with pytest.raises(GitHubError):
        reader.github_token()


def should_send_a_read_and_decode_its_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    answer_with(monkeypatch, {"/pulls/7": (200, {"number": 7})})

    document = reader.request_json("GET", "https://api.github.com/pulls/7", TOKEN, None)

    assert document == {"number": 7}


def should_report_a_status_other_than_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer_with(monkeypatch, {"/pulls/7": (404, {})})

    with pytest.raises(GitHubError):
        reader.request_json("GET", "https://api.github.com/pulls/7", TOKEN, None)


def should_read_one_pull_request(monkeypatch: pytest.MonkeyPatch) -> None:
    answer_with(
        monkeypatch,
        {"/pulls/7": (200, {"number": 7, "head": {"sha": "ab845eb"}})},
    )

    assert reader.read_pull_request("jl-cmd/claude-dev-env", 7, TOKEN) == {
        "number": 7,
        "head": {"sha": "ab845eb"},
    }


def should_report_a_pull_request_answer_of_the_wrong_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer_with(monkeypatch, {"/pulls/7": (200, ["not a pull request"])})

    with pytest.raises(GitHubError):
        reader.read_pull_request("jl-cmd/claude-dev-env", 7, TOKEN)


def should_read_review_threads_over_the_session_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer_with(
        monkeypatch,
        {
            "ccr/review_threads": (
                200,
                [
                    {
                        "path": "scripts/example.py",
                        "resolved": False,
                        "comments": [
                            {"body": "A finding.", "user": {"login": "a-bot"}}
                        ],
                    }
                ],
            )
        },
    )

    all_threads = reader.read_review_threads("jl-cmd/claude-dev-env", 7, TOKEN)

    assert len(all_threads) == 1
    assert all_threads[0].subject == "scripts/example.py"
    assert all_threads[0].all_comments[0].author_login == "a-bot"


def should_fall_back_to_the_graphql_query(monkeypatch: pytest.MonkeyPatch) -> None:
    all_requested_urls = answer_with(
        monkeypatch,
        {
            "ccr/review_threads": (404, {}),
            "graphql": (
                200,
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "nodes": [
                                        {
                                            "path": "scripts/example.py",
                                            "isResolved": True,
                                            "isOutdated": False,
                                            "comments": {"nodes": []},
                                        }
                                    ]
                                }
                            }
                        }
                    }
                },
            ),
        },
    )

    all_threads = reader.read_review_threads("jl-cmd/claude-dev-env", 7, TOKEN)

    assert [each.is_resolved for each in all_threads] == [True]
    assert any("graphql" in each_url for each_url in all_requested_urls)


def should_report_a_graphql_answer_carrying_no_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer_with(
        monkeypatch,
        {
            "ccr/review_threads": (404, {}),
            "graphql": (200, {"errors": [{"message": "refused"}]}),
        },
    )

    with pytest.raises(GitHubError):
        reader.read_review_threads("jl-cmd/claude-dev-env", 7, TOKEN)


def should_read_the_approvals_conclusion_on_a_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer_with(
        monkeypatch,
        {
            "check-runs": (
                200,
                {
                    "check_runs": [
                        {"name": APPROVALS_CHECK_NAME, "conclusion": "failure"}
                    ]
                },
            )
        },
    )

    conclusion = reader.read_approvals_conclusion(
        "jl-cmd/claude-dev-env", "ab845eb", TOKEN
    )

    assert conclusion == "failure"


def should_report_a_check_run_answer_of_the_wrong_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer_with(monkeypatch, {"check-runs": (200, {"check_runs": "none"})})

    with pytest.raises(GitHubError):
        reader.read_approvals_conclusion("jl-cmd/claude-dev-env", "ab845eb", TOKEN)
