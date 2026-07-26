#!/usr/bin/env python3
"""Comment on and close source_pr_number after a full stacked split lands.

::

    supersede_source_pr(
        source_pr_number=99,
        all_child_pr_urls=["https://github.com/o/r/pull/10", "..."],
        planned_slice_count=2,
        should_create_prs=True,
        should_supersede=True,
    )
    {"commented": true, "closed": true, "child_pr_numbers": [10, 11], "skipped": false}

Runs only when every planned slice has a draft PR URL. Uses ``gh pr comment
--body-file`` then ``gh pr close``. Leaves the source branch on the remote.
"""

from __future__ import annotations

import json
from pathlib import Path

from split_pr_process_runner import run_gh, write_markdown_body_file
from split_pr_script_types import JsonObject
from split_pr_scripts_constants.config.common_constants import (
    BLANK_LINE,
    GH_JSON_FLAG,
    GH_PR,
    GH_VIEW,
    PATH_SEPARATOR,
    PAYLOAD_KEY_ERROR,
)
from split_pr_scripts_constants.config.execute_constants import (
    EMPTY_JSON_OBJECT_TEXT,
    ERROR_SUPERSEDE_CLOSE_FAILED,
    ERROR_SUPERSEDE_COMMENT_FAILED,
    ERROR_SUPERSEDE_VIEW_FAILED,
    ERROR_SUPERSEDE_VIEW_JSON,
    GH_BODY_FILE,
    GH_CLOSE,
    GH_COMMENT,
    GH_COMMENT_BODY_FIELD,
    GH_COMMENTS_FIELD,
    GH_STATE_CLOSED,
    GH_STATE_FIELD,
    GH_VIEW_FIELDS,
    MINIMUM_SLICES_FOR_SUPERSEDE,
    NEWLINE,
    PAYLOAD_KEY_CHILD_PR_NUMBERS,
    PAYLOAD_KEY_CLOSED,
    PAYLOAD_KEY_COMMENTED,
    PAYLOAD_KEY_SKIP_REASON,
    PAYLOAD_KEY_SKIPPED,
    PR_URL_NUMBER_MARKER,
    SUPERSEDE_HEADING,
    SUPERSEDE_INTRO,
    SUPERSEDE_LIST_ITEM_TEMPLATE,
    SUPERSEDE_MERGE_ORDER_LABEL,
    SUPERSEDE_MERGE_ORDER_SEPARATOR,
    SUPERSEDE_PR_HASH_PREFIX,
    SUPERSEDE_SKIP_ALREADY_DONE,
    SUPERSEDE_SKIP_ATOMIC,
    SUPERSEDE_SKIP_CREATE_PRS_OFF,
    SUPERSEDE_SKIP_DISABLED,
    SUPERSEDE_SKIP_NO_CHILD_URLS,
    SUPERSEDE_SKIP_PARTIAL,
    SUPERSEDE_UNKNOWN_PR_NUMBER,
)


def extract_pr_number_from_url(pr_url: str) -> int | None:
    """Return the pull number from a GitHub PR URL.

    Args:
        pr_url: Full or partial PR URL containing ``/pull/<n>``.

    Returns:
        Integer PR number, or None when the marker is absent or not numeric.
    """
    marker_index = pr_url.find(PR_URL_NUMBER_MARKER)
    if marker_index < 0:
        return None
    number_text = pr_url[marker_index + len(PR_URL_NUMBER_MARKER) :]
    number_token = number_text.split(PATH_SEPARATOR, maxsplit=1)[0].strip()
    if not number_token.isdigit():
        return None
    return int(number_token)


def build_supersede_comment_body(
    all_child_pr_numbers: list[int],
    all_child_pr_urls: list[str],
) -> str:
    """Build the supersede comment markdown for source_pr_number.

    Args:
        all_child_pr_numbers: Ordered child PR numbers matching the stack.
        all_child_pr_urls: Ordered permanent GitHub URLs for those PRs.

    Returns:
        Markdown body with heading, merge order, and numbered child links.
    """
    merge_order = SUPERSEDE_MERGE_ORDER_SEPARATOR.join(
        f"{SUPERSEDE_PR_HASH_PREFIX}{each_number}"
        for each_number in all_child_pr_numbers
    )
    all_list_lines = [
        _format_child_pr_line(each_position, each_url)
        for each_position, each_url in enumerate(all_child_pr_urls, start=1)
    ]
    return NEWLINE.join(
        [
            SUPERSEDE_HEADING,
            BLANK_LINE,
            SUPERSEDE_INTRO,
            BLANK_LINE,
            f"{SUPERSEDE_MERGE_ORDER_LABEL} {merge_order}",
            BLANK_LINE,
            *all_list_lines,
            BLANK_LINE,
        ]
    )


def _format_child_pr_line(position: int, pr_url: str) -> str:
    pr_number = extract_pr_number_from_url(pr_url)
    number_label = (
        SUPERSEDE_UNKNOWN_PR_NUMBER if pr_number is None else str(pr_number)
    )
    return SUPERSEDE_LIST_ITEM_TEMPLATE % (position, number_label, pr_url)


def resolve_supersede_skip_reason(
    planned_slice_count: int,
    all_child_pr_urls: list[str],
    should_create_prs: bool,
    should_supersede: bool,
) -> str | None:
    """Return a skip reason when supersede must not run, else None.

    Args:
        planned_slice_count: Number of slices in the verified plan.
        all_child_pr_urls: Draft PR URLs created this execute (may be partial).
        should_create_prs: Whether execute opened draft PRs on GitHub.
        should_supersede: Explicit supersede switch from the CLI.

    Returns:
        Stable skip-reason string, or None when supersede may proceed.
    """
    if not should_supersede:
        return SUPERSEDE_SKIP_DISABLED
    if not should_create_prs:
        return SUPERSEDE_SKIP_CREATE_PRS_OFF
    if planned_slice_count < MINIMUM_SLICES_FOR_SUPERSEDE:
        return SUPERSEDE_SKIP_ATOMIC
    if not all_child_pr_urls:
        return SUPERSEDE_SKIP_NO_CHILD_URLS
    if len(all_child_pr_urls) < planned_slice_count:
        return SUPERSEDE_SKIP_PARTIAL
    return None


def supersede_source_pr(
    source_pr_number: int,
    all_child_pr_urls: list[str],
    planned_slice_count: int,
    should_create_prs: bool,
    should_supersede: bool,
    repo: str | None = None,
    repo_root: Path | None = None,
) -> JsonObject:
    """Comment merge order on source_pr_number and close it as superseded.

    Args:
        source_pr_number: Open pull request that was file-split.
        all_child_pr_urls: Ordered draft PR URLs for every planned slice.
        planned_slice_count: Slice count from the verified plan.
        should_create_prs: True when this execute opened draft PRs.
        should_supersede: False disables supersede even when drafts exist.
        repo: Optional ``owner/name`` for ``gh --repo``.
        repo_root: Working directory for ``gh`` (repository root).

    Returns:
        Payload with ``commented``, ``closed``, ``child_pr_numbers``, and
        skip metadata when supersede did not run.

    Raises:
        RuntimeError: When ``gh pr view``, ``comment``, or ``close`` fails.
    """
    skip_reason = resolve_supersede_skip_reason(
        planned_slice_count=planned_slice_count,
        all_child_pr_urls=all_child_pr_urls,
        should_create_prs=should_create_prs,
        should_supersede=should_supersede,
    )
    all_child_pr_numbers = _collect_child_pr_numbers(all_child_pr_urls)
    if skip_reason is not None:
        return build_skipped_payload(all_child_pr_numbers, skip_reason)

    working_directory = str(repo_root) if repo_root is not None else None
    if _is_already_superseded(
        source_pr_number=source_pr_number,
        repo=repo,
        working_directory=working_directory,
    ):
        return build_skipped_payload(all_child_pr_numbers, SUPERSEDE_SKIP_ALREADY_DONE)

    _post_supersede_comment(
        source_pr_number=source_pr_number,
        all_child_pr_numbers=all_child_pr_numbers,
        all_child_pr_urls=all_child_pr_urls,
        repo=repo,
        working_directory=working_directory,
    )
    run_gh(
        [GH_PR, GH_CLOSE, str(source_pr_number)],
        repo=repo,
        working_directory=working_directory,
        error_template=ERROR_SUPERSEDE_CLOSE_FAILED,
        all_error_context=(source_pr_number,),
    )
    return {
        PAYLOAD_KEY_COMMENTED: True,
        PAYLOAD_KEY_CLOSED: True,
        PAYLOAD_KEY_CHILD_PR_NUMBERS: all_child_pr_numbers,
        PAYLOAD_KEY_SKIPPED: False,
    }


def _post_supersede_comment(
    source_pr_number: int,
    all_child_pr_numbers: list[int],
    all_child_pr_urls: list[str],
    repo: str | None,
    working_directory: str | None,
) -> None:
    body_path = write_markdown_body_file(
        build_supersede_comment_body(
            all_child_pr_numbers=all_child_pr_numbers,
            all_child_pr_urls=all_child_pr_urls,
        )
    )
    try:
        run_gh(
            [GH_PR, GH_COMMENT, str(source_pr_number), GH_BODY_FILE, body_path],
            repo=repo,
            working_directory=working_directory,
            error_template=ERROR_SUPERSEDE_COMMENT_FAILED,
            all_error_context=(source_pr_number,),
        )
    finally:
        Path(body_path).unlink(missing_ok=True)


def _collect_child_pr_numbers(all_child_pr_urls: list[str]) -> list[int]:
    all_numbers: list[int] = []
    for each_url in all_child_pr_urls:
        pr_number = extract_pr_number_from_url(each_url)
        if pr_number is not None:
            all_numbers.append(pr_number)
    return all_numbers


def _build_unsuperseded_payload(
    all_child_pr_numbers: list[int],
    is_skipped: bool,
) -> JsonObject:
    return {
        PAYLOAD_KEY_COMMENTED: False,
        PAYLOAD_KEY_CLOSED: False,
        PAYLOAD_KEY_CHILD_PR_NUMBERS: all_child_pr_numbers,
        PAYLOAD_KEY_SKIPPED: is_skipped,
    }


def build_skipped_payload(
    all_child_pr_numbers: list[int],
    skip_reason: str,
) -> JsonObject:
    """Return the payload that reports supersede deliberately stood down.

    Args:
        all_child_pr_numbers: Child PR numbers parsed from the stack URLs.
        skip_reason: Stable reason string naming why supersede stood down.

    Returns:
        Payload with ``skipped`` true and the reason attached.
    """
    skipped_payload = _build_unsuperseded_payload(all_child_pr_numbers, is_skipped=True)
    skipped_payload[PAYLOAD_KEY_SKIP_REASON] = skip_reason
    return skipped_payload


def build_failed_payload(
    all_child_pr_urls: list[str],
    error_text: str,
) -> JsonObject:
    """Return the payload that reports supersede raised before it finished.

    ::

        build_failed_payload(["https://github.com/o/r/pull/10"], "gh exploded")
        # ok: {"commented": false, "closed": false, "child_pr_numbers": [10],
        #      "skipped": false, "error": "gh exploded"}

    A raised supersede leaves the source PR open, so the payload reports
    ``skipped`` false: nothing stood down, the attempt failed.

    Args:
        all_child_pr_urls: Draft PR URLs created for the stack.
        error_text: Message from the exception supersede raised.

    Returns:
        Payload carrying the child PR numbers and the error text.
    """
    failed_payload = _build_unsuperseded_payload(
        _collect_child_pr_numbers(all_child_pr_urls),
        is_skipped=False,
    )
    failed_payload[PAYLOAD_KEY_ERROR] = error_text
    return failed_payload


def _is_already_superseded(
    source_pr_number: int,
    repo: str | None,
    working_directory: str | None,
) -> bool:
    view_json_text = run_gh(
        [GH_PR, GH_VIEW, str(source_pr_number), GH_JSON_FLAG, GH_VIEW_FIELDS],
        repo=repo,
        working_directory=working_directory,
        error_template=ERROR_SUPERSEDE_VIEW_FAILED,
        all_error_context=(source_pr_number,),
    )
    view_payload = _parse_view_payload(source_pr_number, view_json_text)
    if view_payload is None:
        return False
    state_text = str(view_payload.get(GH_STATE_FIELD) or "")
    if state_text.upper() != GH_STATE_CLOSED:
        return False
    return _holds_supersede_comment(view_payload.get(GH_COMMENTS_FIELD))


def _parse_view_payload(source_pr_number: int, view_json_text: str) -> JsonObject | None:
    try:
        view_payload: object = json.loads(view_json_text or EMPTY_JSON_OBJECT_TEXT)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            ERROR_SUPERSEDE_VIEW_JSON % (source_pr_number, error)
        ) from error
    if not isinstance(view_payload, dict):
        return None
    return view_payload


def _holds_supersede_comment(all_comments: object) -> bool:
    if not isinstance(all_comments, list):
        return False
    for each_comment in all_comments:
        if not isinstance(each_comment, dict):
            continue
        body_text = str(each_comment.get(GH_COMMENT_BODY_FIELD) or "")
        if SUPERSEDE_HEADING in body_text:
            return True
    return False
