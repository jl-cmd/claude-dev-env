from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import review_closure as command
import review_closure_model as model
from pr_verification.github_parsing import GitHubError

SLUG = "jl-cmd/claude-dev-env"
PULL_REQUEST = {
    "number": 7,
    "head": {"sha": "ab845eb"},
    "user": {"login": "claude[bot]"},
}


def bot_comment(body: str = "This call drops the return value.") -> model.ReviewComment:
    return model.ReviewComment(author_login="qodo-merge-pro[bot]", body=body)


def agent_comment() -> model.ReviewComment:
    return model.ReviewComment(author_login="claude[bot]", body="Fixed and pushed.")


def unanswered_thread() -> model.ReviewThread:
    return model.ReviewThread(
        subject="scripts/example.py",
        is_resolved=False,
        is_outdated=False,
        all_comments=(bot_comment(),),
    )


def answered_thread() -> model.ReviewThread:
    return model.ReviewThread(
        subject="scripts/example.py",
        is_resolved=False,
        is_outdated=False,
        all_comments=(bot_comment(), agent_comment()),
    )


def stub_reads(
    monkeypatch: pytest.MonkeyPatch,
    all_threads: tuple[model.ReviewThread, ...],
    conclusion: str | None = "success",
) -> None:
    monkeypatch.setattr(command, "github_token", lambda: "a-token")
    monkeypatch.setattr(command, "read_pull_request", lambda *_: PULL_REQUEST)
    monkeypatch.setattr(command, "read_review_threads", lambda *_: all_threads)
    monkeypatch.setattr(command, "read_approvals_conclusion", lambda *_: conclusion)


def should_build_a_parser_that_collects_extra_driver_logins() -> None:
    parsed = command.build_parser().parse_args(
        [SLUG, "7", "--driver-login", "JonEcho", "--driver-login", "claude[bot]"]
    )

    assert parsed.slug == SLUG
    assert parsed.number == 7
    assert parsed.driver_login == ["JonEcho", "claude[bot]"]


def should_report_an_unanswered_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_reads(monkeypatch, (unanswered_thread(),))

    report = command.closure_report(SLUG, 7, [], "a-token")

    assert report.verdict.startswith("OPEN")
    assert [each.subject for each in report.all_findings] == ["scripts/example.py"]


def should_report_an_answered_pull_request_as_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_reads(monkeypatch, (answered_thread(),))

    report = command.closure_report(SLUG, 7, [], "a-token")

    assert report.verdict.startswith("CLOSED")
    assert report.all_findings == ()


def should_exit_one_while_a_finding_waits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stub_reads(monkeypatch, (unanswered_thread(),))

    status = command.main([SLUG, "7"])

    assert status == 1
    assert "scripts/example.py" in capsys.readouterr().out


def should_exit_zero_once_the_finding_is_answered(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stub_reads(monkeypatch, (answered_thread(),))

    status = command.main([SLUG, "7"])

    assert status == 0
    assert capsys.readouterr().out.startswith("CLOSED")


def should_exit_two_when_the_state_could_not_be_read(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(command, "github_token", lambda: "a-token")

    def refuse(*_: object) -> None:
        raise GitHubError("the proxy refused this read")

    monkeypatch.setattr(command, "read_pull_request", refuse)

    status = command.main([SLUG, "7"])

    assert status == 2
    assert "refused" in capsys.readouterr().err
