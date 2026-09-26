"""Decide whether a review finding on a pull request head is answered.

A review bot posts a finding, the agent driving the pull request answers it or
pushes the fix, and the thread closes. Until then the finding waits. These
functions read the review threads, the top-level comments on the pull request,
and the approvals conclusion, and name what waits.

::

    thread: a bot comment, nothing after it     -> open
    thread: a bot comment, then an agent reply  -> closed
    thread: a bot comment, code since replaced  -> closed
    thread: a red circle, resolved in silence   -> open
    top-level: a bot comment, no agent comment  -> open
    top-level: a bot comment, then an agent one -> closed
    top-level: the bot edits after that reply   -> open

A red circle marks a finding a review states as blocking, so resolution alone
leaves it open. The reply says what changed, or why the finding stands.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from dev_env_scripts_constants.review_closure_constants import (
    ALL_BLOCKING_CONCLUSIONS,
    ALL_COMMENT_AUTHOR_KEYS,
    ALL_COMMENT_LIST_KEYS,
    ALL_OUTDATED_KEYS,
    ALL_RESOLVED_KEYS,
    APPROVALS_CHECK_NAME,
    APPROVALS_OPEN_REASON,
    AUTHOR_LOGIN_KEY,
    CHECK_RUN_CONCLUSION_KEY,
    CHECK_RUN_NAME_KEY,
    CLOSED_DETAIL,
    CLOSED_VERDICT_LABEL,
    COMMENT_BODY_KEY,
    COMMENT_IDENTIFIER_KEY,
    COMMENT_IDS_KEY,
    COMMENT_NODES_KEY,
    CREATED_AT_KEY,
    HEAD_KEY,
    HTML_URL_KEY,
    NUMBER_KEY,
    OPEN_DETAIL_TEMPLATE,
    OPEN_VERDICT_LABEL,
    RED_CIRCLE_MARKER,
    RED_CIRCLE_OPEN_REASON,
    SHA_KEY,
    SHORT_SHA_LENGTH,
    THREAD_PATH_KEY,
    TOP_LEVEL_OPEN_REASON_TEMPLATE,
    UNANSWERED_OPEN_REASON,
    UNNAMED_THREAD_SUBJECT,
    UPDATED_AT_KEY,
    USER_KEY,
    VERDICT_LINE_TEMPLATE,
)


@dataclass(frozen=True)
class ReviewComment:
    """One comment inside a review thread."""

    author_login: str
    body: str


@dataclass(frozen=True)
class ReviewThread:
    """One review thread, as the closure decision reads it."""

    subject: str
    is_resolved: bool
    is_outdated: bool
    all_comments: tuple[ReviewComment, ...]


@dataclass(frozen=True)
class TopLevelComment:
    """One comment on the pull request itself, outside any review thread."""

    identifier: object
    author_login: str
    created_at: datetime
    updated_at: datetime
    url: str


@dataclass(frozen=True)
class OpenFinding:
    """One finding that still waits on the agent driving the pull request."""

    subject: str
    reason: str


def carries_red_circle(thread: ReviewThread) -> bool:
    """Say whether a thread opens with a blocking finding.

    Args:
        thread: The review thread to read.

    Returns:
        True when its first comment carries the red circle a review marks a
        blocking finding with.
    """
    if not thread.all_comments:
        return False
    return RED_CIRCLE_MARKER in thread.all_comments[0].body


def has_driver_reply(thread: ReviewThread, all_driver_logins: frozenset[str]) -> bool:
    """Say whether the driving agent answered a thread.

    Args:
        thread: The review thread to read.
        all_driver_logins: The logins whose comments count as the answer.

    Returns:
        True when any comment after the first carries one of those logins.
    """
    return any(
        each_comment.author_login in all_driver_logins
        for each_comment in thread.all_comments[1:]
    )


def opened_by_driver(thread: ReviewThread, all_driver_logins: frozenset[str]) -> bool:
    """Say whether the driving agent started a thread itself.

    Args:
        thread: The review thread to read.
        all_driver_logins: The logins that count as the driving agent.

    Returns:
        True when its first comment carries one of those logins.
    """
    return bool(thread.all_comments) and (
        thread.all_comments[0].author_login in all_driver_logins
    )


def thread_finding(
    thread: ReviewThread, all_driver_logins: frozenset[str]
) -> OpenFinding | None:
    """Decide whether one review thread still waits on the driving agent.

    Args:
        thread: The review thread to judge.
        all_driver_logins: The logins whose comments count as the answer.

    Returns:
        The finding this thread leaves open, or None when it is closed.
    """
    if thread.is_outdated:
        return None
    if opened_by_driver(thread, all_driver_logins):
        return None
    if has_driver_reply(thread, all_driver_logins):
        return None
    if carries_red_circle(thread):
        return OpenFinding(subject=thread.subject, reason=RED_CIRCLE_OPEN_REASON)
    if thread.is_resolved:
        return None
    return OpenFinding(subject=thread.subject, reason=UNANSWERED_OPEN_REASON)


def latest_driver_comment_time(
    all_comments: Iterable[TopLevelComment],
    all_driver_logins: frozenset[str],
) -> datetime | None:
    """Find when the driving agent last posted a top-level comment.

    Args:
        all_comments: The top-level comments on the pull request.
        all_driver_logins: The logins that count as the driving agent.

    Returns:
        The creation time of the driving agent's latest top-level comment, or
        None when it posted none.
    """
    return max(
        (
            each_comment.created_at
            for each_comment in all_comments
            if each_comment.author_login in all_driver_logins
        ),
        default=None,
    )


def top_level_finding(
    comment: TopLevelComment,
    all_driver_logins: frozenset[str],
    latest_driver_time: datetime | None,
) -> OpenFinding | None:
    """Decide whether one top-level comment still waits on the driving agent.

    Args:
        comment: The top-level comment to judge.
        all_driver_logins: The logins whose comments count as the answer.
        latest_driver_time: When the driving agent last posted a top-level
            comment, or None when it posted none.

    Returns:
        The finding this comment leaves open, or None when it is answered.
    """
    if comment.author_login in all_driver_logins:
        return None
    if latest_driver_time is not None and comment.updated_at <= latest_driver_time:
        return None
    return OpenFinding(
        subject=comment.url,
        reason=TOP_LEVEL_OPEN_REASON_TEMPLATE.format(author=comment.author_login),
    )


def top_level_findings(
    all_comments: Iterable[TopLevelComment],
    all_driver_logins: frozenset[str],
) -> tuple[OpenFinding, ...]:
    """Decide which top-level comments still wait on the driving agent.

    The driving agent answers a top-level comment by posting a top-level
    comment of its own. Its latest one answers every comment last touched
    before it, and a comment edited after it waits again.

    Args:
        all_comments: The top-level comments on the pull request.
        all_driver_logins: The logins whose comments count as the answer.

    Returns:
        One finding per comment from another account that was posted or
        edited after the driving agent's latest top-level comment.
    """
    all_listed_comments = tuple(all_comments)
    latest_driver_time = latest_driver_comment_time(
        all_listed_comments, all_driver_logins
    )
    return tuple(
        each_finding
        for each_finding in (
            top_level_finding(each_comment, all_driver_logins, latest_driver_time)
            for each_comment in all_listed_comments
        )
        if each_finding is not None
    )


def all_open_findings(
    all_threads: Iterable[ReviewThread],
    all_top_level_comments: Iterable[TopLevelComment],
    all_driver_logins: frozenset[str],
    approvals_conclusion_text: str | None,
) -> tuple[OpenFinding, ...]:
    """Collect every finding on a pull request head that waits on its agent.

    Args:
        all_threads: The review threads on the pull request.
        all_top_level_comments: The comments on the pull request itself.
        all_driver_logins: The logins whose comments count as the answer.
        approvals_conclusion_text: What the Claude Approvals check run on the
            head concluded, or None where that check does not run.

    Returns:
        One finding per open review thread, then one per waiting top-level
        comment, then the approvals finding when that check reports a
        blocking row on this commit.
    """
    all_findings = [
        each_finding
        for each_finding in (
            thread_finding(each_thread, all_driver_logins)
            for each_thread in all_threads
        )
        if each_finding is not None
    ]
    all_findings.extend(top_level_findings(all_top_level_comments, all_driver_logins))
    if approvals_conclusion_text in ALL_BLOCKING_CONCLUSIONS:
        all_findings.append(
            OpenFinding(subject=APPROVALS_CHECK_NAME, reason=APPROVALS_OPEN_REASON)
        )
    return tuple(all_findings)


def head_sha(all_pull_request_fields: Mapping[str, object]) -> str:
    """Read the head commit a pull request reports.

    Args:
        all_pull_request_fields: The pull request as GitHub reports it.

    Returns:
        The head commit, or an empty string when the field is absent.
    """
    all_head_fields = all_pull_request_fields.get(HEAD_KEY)
    if isinstance(all_head_fields, Mapping):
        return str(all_head_fields.get(SHA_KEY) or "")
    return ""


def verdict_line(
    slug: str,
    all_pull_request_fields: Mapping[str, object],
    all_findings: Sequence[OpenFinding],
) -> str:
    """Build the one line the command prints for a pull request.

    Args:
        slug: The repository as ``owner/name``.
        all_pull_request_fields: The pull request the verdict describes.
        all_findings: The findings that still wait on the driving agent.

    Returns:
        A line naming the verdict, the pull request, its head commit, and
        either the closed detail or how many findings wait.
    """
    return VERDICT_LINE_TEMPLATE.format(
        label=OPEN_VERDICT_LABEL if all_findings else CLOSED_VERDICT_LABEL,
        slug=slug,
        number=all_pull_request_fields.get(NUMBER_KEY),
        sha=head_sha(all_pull_request_fields)[:SHORT_SHA_LENGTH],
        detail=_verdict_detail(all_findings),
    )


def _verdict_detail(all_findings: Sequence[OpenFinding]) -> str:
    if not all_findings:
        return CLOSED_DETAIL
    return OPEN_DETAIL_TEMPLATE.format(count=len(all_findings))


def driver_logins(
    all_pull_request_fields: Mapping[str, object],
    all_extra_logins: Iterable[str],
) -> frozenset[str]:
    """Collect the logins whose comments answer a finding.

    Args:
        all_pull_request_fields: The pull request, carrying the account that
            opened it.
        all_extra_logins: Logins named on the command line.

    Returns:
        The account that opened the pull request, with every extra login.
    """
    all_logins = {each_login for each_login in all_extra_logins if each_login}
    all_author_fields = all_pull_request_fields.get(USER_KEY)
    if isinstance(all_author_fields, Mapping):
        author_login = all_author_fields.get(AUTHOR_LOGIN_KEY)
        if author_login:
            all_logins.add(str(author_login))
    return frozenset(all_logins)


def parse_thread(
    all_thread_fields: Mapping[str, object],
    all_comment_records_by_id: Mapping[object, Mapping[str, object]] | None = None,
) -> ReviewThread:
    """Read one review thread from either route's answer.

    The GraphQL answer nests each thread's comments. The session route names
    them by identifier instead, so that route's caller passes the comments it
    read for the pull request and this joins the two.

    Args:
        all_thread_fields: The thread as the REST route or the GraphQL query
            reports it.
        all_comment_records_by_id: The pull request's review comments, keyed
            by identifier, for a thread that names its comments by identifier.

    Returns:
        The thread in the shape the closure decision reads.
    """
    return ReviewThread(
        subject=str(all_thread_fields.get(THREAD_PATH_KEY) or UNNAMED_THREAD_SUBJECT),
        is_resolved=_any_flag(all_thread_fields, ALL_RESOLVED_KEYS),
        is_outdated=_any_flag(all_thread_fields, ALL_OUTDATED_KEYS),
        all_comments=tuple(
            _parse_comment(each_record)
            for each_record in _comment_records(
                all_thread_fields, all_comment_records_by_id or {}
            )
        ),
    )


def comment_records_by_id(
    all_comment_records: Iterable[object],
) -> dict[object, Mapping[str, object]]:
    """Key a pull request's review comments by their identifiers.

    Args:
        all_comment_records: The review comments GitHub reports.

    Returns:
        Each comment under its identifier.
    """
    return {
        each_record[COMMENT_IDENTIFIER_KEY]: each_record
        for each_record in all_comment_records
        if isinstance(each_record, Mapping) and COMMENT_IDENTIFIER_KEY in each_record
    }


def parse_top_level_comment(
    all_comment_fields: Mapping[str, object],
) -> TopLevelComment:
    """Read one top-level comment from the REST answer.

    Args:
        all_comment_fields: The comment as the issue comments route reports it.

    Returns:
        The comment in the shape the closure decision reads.

    Raises:
        ValueError: A timestamp is missing or does not parse.
    """
    return TopLevelComment(
        identifier=all_comment_fields.get(COMMENT_IDENTIFIER_KEY),
        author_login=_comment_author_login(all_comment_fields),
        created_at=datetime.fromisoformat(str(all_comment_fields.get(CREATED_AT_KEY))),
        updated_at=datetime.fromisoformat(str(all_comment_fields.get(UPDATED_AT_KEY))),
        url=str(all_comment_fields.get(HTML_URL_KEY) or ""),
    )


def approvals_conclusion(all_check_runs: Iterable[object]) -> str | None:
    """Find what the Claude Approvals check reports on a commit.

    Args:
        all_check_runs: The check runs GitHub reports for the head commit.

    Returns:
        That check run's conclusion, or None where the repository does not
        run it and where it has not concluded.
    """
    for each_run in all_check_runs:
        if (
            isinstance(each_run, Mapping)
            and each_run.get(CHECK_RUN_NAME_KEY) == APPROVALS_CHECK_NAME
        ):
            conclusion = each_run.get(CHECK_RUN_CONCLUSION_KEY)
            return None if conclusion is None else str(conclusion)
    return None


def _comment_records(
    all_thread_fields: Mapping[str, object],
    all_comment_records_by_id: Mapping[object, Mapping[str, object]],
) -> list[Mapping[str, object]]:
    all_identifiers = all_thread_fields.get(COMMENT_IDS_KEY)
    if isinstance(all_identifiers, list):
        return [
            all_comment_records_by_id[each_identifier]
            for each_identifier in all_identifiers
            if each_identifier in all_comment_records_by_id
        ]
    for each_key in ALL_COMMENT_LIST_KEYS:
        found = all_thread_fields.get(each_key)
        if isinstance(found, Mapping):
            found = found.get(COMMENT_NODES_KEY)
        if isinstance(found, list):
            return [each for each in found if isinstance(each, Mapping)]
    return []


def _parse_comment(all_comment_fields: Mapping[str, object]) -> ReviewComment:
    return ReviewComment(
        author_login=_comment_author_login(all_comment_fields),
        body=str(all_comment_fields.get(COMMENT_BODY_KEY) or ""),
    )


def _comment_author_login(all_comment_fields: Mapping[str, object]) -> str:
    for each_key in ALL_COMMENT_AUTHOR_KEYS:
        all_author_fields = all_comment_fields.get(each_key)
        if isinstance(all_author_fields, Mapping):
            return str(all_author_fields.get(AUTHOR_LOGIN_KEY) or "")
    return ""


def _any_flag(all_fields: Mapping[str, object], all_keys: Sequence[str]) -> bool:
    return any(all_fields.get(each_key) for each_key in all_keys)
