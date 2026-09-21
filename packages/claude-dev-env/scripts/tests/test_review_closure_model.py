from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import review_closure_model as model
from dev_env_scripts_constants.review_closure_constants import (
    APPROVALS_CHECK_NAME,
    APPROVALS_OPEN_REASON,
    RED_CIRCLE_MARKER,
    RED_CIRCLE_OPEN_REASON,
    UNANSWERED_OPEN_REASON,
    UNNAMED_THREAD_SUBJECT,
)

DRIVING_AGENT = frozenset({"claude[bot]"})
REVIEW_BOT = "qodo-merge-pro[bot]"


def thread(
    *,
    all_comments: tuple[model.ReviewComment, ...],
    is_resolved: bool = False,
    is_outdated: bool = False,
    subject: str = "scripts/example.py",
) -> model.ReviewThread:
    return model.ReviewThread(
        subject=subject,
        is_resolved=is_resolved,
        is_outdated=is_outdated,
        all_comments=all_comments,
    )


def bot_comment(body: str = "This call drops the return value.") -> model.ReviewComment:
    return model.ReviewComment(author_login=REVIEW_BOT, body=body)


def agent_comment(body: str = "Fixed in the next push.") -> model.ReviewComment:
    return model.ReviewComment(author_login="claude[bot]", body=body)


def should_report_an_unanswered_thread_as_open() -> None:
    finding = model.thread_finding(thread(all_comments=(bot_comment(),)), DRIVING_AGENT)

    assert finding == model.OpenFinding(
        subject="scripts/example.py", reason=UNANSWERED_OPEN_REASON
    )


def should_close_a_thread_the_driving_agent_replied_to() -> None:
    answered = thread(all_comments=(bot_comment(), agent_comment()))

    assert model.thread_finding(answered, DRIVING_AGENT) is None


def should_leave_a_thread_open_when_only_another_bot_replied() -> None:
    other_bot = model.ReviewComment(author_login="graphite[bot]", body="Same here.")
    noisy = thread(all_comments=(bot_comment(), other_bot))

    assert model.thread_finding(noisy, DRIVING_AGENT) is not None


def should_close_an_outdated_thread_without_a_reply() -> None:
    replaced = thread(all_comments=(bot_comment(),), is_outdated=True)

    assert model.thread_finding(replaced, DRIVING_AGENT) is None


def should_close_a_resolved_ordinary_thread() -> None:
    resolved = thread(all_comments=(bot_comment(),), is_resolved=True)

    assert model.thread_finding(resolved, DRIVING_AGENT) is None


def should_keep_a_resolved_red_circle_finding_open() -> None:
    blocking = thread(
        all_comments=(bot_comment(f"{RED_CIRCLE_MARKER} This drops user input."),),
        is_resolved=True,
    )

    finding = model.thread_finding(blocking, DRIVING_AGENT)

    assert finding == model.OpenFinding(
        subject="scripts/example.py", reason=RED_CIRCLE_OPEN_REASON
    )


def should_close_a_red_circle_finding_the_agent_answered() -> None:
    answered = thread(
        all_comments=(
            bot_comment(f"{RED_CIRCLE_MARKER} This drops user input."),
            agent_comment(),
        )
    )

    assert model.thread_finding(answered, DRIVING_AGENT) is None


def should_close_a_red_circle_finding_a_push_replaced() -> None:
    replaced = thread(
        all_comments=(bot_comment(f"{RED_CIRCLE_MARKER} This drops user input."),),
        is_outdated=True,
    )

    assert model.thread_finding(replaced, DRIVING_AGENT) is None


def should_close_a_thread_the_driving_agent_opened() -> None:
    own = thread(all_comments=(agent_comment("Reading this back for the reviewer."),))

    assert model.thread_finding(own, DRIVING_AGENT) is None


def should_report_the_driving_agent_as_the_thread_author() -> None:
    own = thread(all_comments=(agent_comment(),))

    assert model.opened_by_driver(own, DRIVING_AGENT) is True
    assert model.opened_by_driver(thread(all_comments=()), DRIVING_AGENT) is False


def should_report_a_reply_from_the_driving_agent() -> None:
    answered = thread(all_comments=(bot_comment(), agent_comment()))

    assert model.has_driver_reply(answered, DRIVING_AGENT) is True
    assert (
        model.has_driver_reply(thread(all_comments=(bot_comment(),)), DRIVING_AGENT)
        is False
    )


def should_report_a_blocking_approvals_row_as_open() -> None:
    all_findings = model.all_open_findings((), DRIVING_AGENT, "failure")

    assert all_findings == (
        model.OpenFinding(subject=APPROVALS_CHECK_NAME, reason=APPROVALS_OPEN_REASON),
    )


def should_pass_when_approvals_succeeds_and_no_thread_waits() -> None:
    answered = thread(all_comments=(bot_comment(), agent_comment()))

    assert model.all_open_findings((answered,), DRIVING_AGENT, "success") == ()


def should_pass_where_the_approvals_check_does_not_run() -> None:
    assert model.all_open_findings((), DRIVING_AGENT, None) == ()


def should_report_every_open_thread_and_the_approvals_row() -> None:
    first = thread(all_comments=(bot_comment(),), subject="scripts/first.py")
    second = thread(all_comments=(bot_comment(),), subject="scripts/second.py")

    all_findings = model.all_open_findings(
        (first, second), DRIVING_AGENT, "action_required"
    )

    assert [each.subject for each in all_findings] == [
        "scripts/first.py",
        "scripts/second.py",
        APPROVALS_CHECK_NAME,
    ]


def should_read_a_graphql_thread_record() -> None:
    parsed = model.parse_thread(
        {
            "path": "scripts/example.py",
            "isResolved": False,
            "isOutdated": True,
            "comments": {
                "nodes": [
                    {"body": "A finding.", "author": {"login": REVIEW_BOT}},
                    {"body": "Answered.", "author": {"login": "claude[bot]"}},
                ]
            },
        }
    )

    assert parsed == model.ReviewThread(
        subject="scripts/example.py",
        is_resolved=False,
        is_outdated=True,
        all_comments=(
            model.ReviewComment(author_login=REVIEW_BOT, body="A finding."),
            model.ReviewComment(author_login="claude[bot]", body="Answered."),
        ),
    )


def should_read_a_rest_thread_record() -> None:
    parsed = model.parse_thread(
        {
            "resolved": True,
            "outdated": False,
            "comments": [{"body": "A finding.", "user": {"login": REVIEW_BOT}}],
        }
    )

    assert parsed == model.ReviewThread(
        subject=UNNAMED_THREAD_SUBJECT,
        is_resolved=True,
        is_outdated=False,
        all_comments=(model.ReviewComment(author_login=REVIEW_BOT, body="A finding."),),
    )


def should_read_a_thread_that_carries_no_comments() -> None:
    parsed = model.parse_thread({"path": "scripts/example.py"})

    assert parsed.all_comments == ()
    assert model.carries_red_circle(parsed) is False


def should_find_the_approvals_conclusion_among_the_check_runs() -> None:
    all_check_runs = [
        {"name": "Python suite (ubuntu)", "conclusion": "success"},
        {"name": APPROVALS_CHECK_NAME, "conclusion": "failure"},
    ]

    assert model.approvals_conclusion(all_check_runs) == "failure"


def should_report_no_conclusion_where_approvals_does_not_run() -> None:
    assert model.approvals_conclusion([{"name": "Python suite (ubuntu)"}]) is None


def should_count_the_pull_request_author_as_the_driving_agent() -> None:
    all_logins = model.driver_logins({"user": {"login": "claude[bot]"}}, [])

    assert all_logins == frozenset({"claude[bot]"})


def should_add_each_login_named_on_the_command_line() -> None:
    all_logins = model.driver_logins({"user": {"login": "claude[bot]"}}, ["JonEcho"])

    assert all_logins == frozenset({"claude[bot]", "JonEcho"})


def should_read_the_head_commit_from_the_pull_request() -> None:
    assert model.head_sha({"head": {"sha": "ab845eb"}}) == "ab845eb"
    assert model.head_sha({}) == ""


def should_name_the_open_count_in_the_verdict_line() -> None:
    line = model.verdict_line(
        "jl-cmd/claude-dev-env",
        {"number": 1442, "head": {"sha": "ab845ebc0ffee11"}},
        (model.OpenFinding(subject="scripts/example.py", reason="waiting"),),
    )

    assert line.startswith("OPEN jl-cmd/claude-dev-env#1442 ab845eb :: 1 review")


def should_name_the_closed_state_in_the_verdict_line() -> None:
    line = model.verdict_line(
        "jl-cmd/claude-dev-env",
        {"number": 1442, "head": {"sha": "ab845ebc0ffee11"}},
        (),
    )

    assert line.startswith("CLOSED jl-cmd/claude-dev-env#1442 ab845eb ::")
