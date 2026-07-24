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
import subprocess
from pathlib import Path

from gh_body_comment import run_gh_pr_comment, write_markdown_body_file
from split_pr_scripts_constants.config.execute_constants import (
    ERROR_SUPERSEDE_CLOSE_FAILED,
    ERROR_SUPERSEDE_COMMENT_FAILED,
    ERROR_SUPERSEDE_VIEW_FAILED,
    GH_CLOSE,
    GH_COMMAND,
    GH_COMMENT_BODY_FIELD,
    GH_COMMENTS_FIELD,
    GH_JSON,
    GH_PR,
    GH_REPO_FLAG,
    GH_STATE_CLOSED,
    GH_STATE_FIELD,
    GH_VIEW,
    GH_VIEW_FIELDS,
    MINIMUM_SLICES_FOR_SUPERSEDE,
    PAYLOAD_KEY_CHILD_PR_NUMBERS,
    PAYLOAD_KEY_CLOSED,
    PAYLOAD_KEY_COMMENTED,
    PAYLOAD_KEY_SKIPPED,
    PAYLOAD_KEY_SKIP_REASON,
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
    NEWLINE,
)

JsonObject = dict[str, object]


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
    number_token = number_text.split("/", maxsplit=1)[0].strip()
    if not number_token.isdigit():
        return None
    return int(number_token)


def collect_pr_numbers_from_urls(all_child_pr_urls: list[str]) -> list[int]:
    """Return PR numbers parsed from ordered GitHub pull URLs.

    Args:
        all_child_pr_urls: PR URLs that may contain ``/pull/<n>``.

    Returns:
        Ordered list of integer PR numbers found in the URLs.
    """
    all_numbers: list[int] = []
    for each_url in all_child_pr_urls:
        pr_number = extract_pr_number_from_url(each_url)
        if pr_number is not None:
            all_numbers.append(pr_number)
    return all_numbers


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
        SUPERSEDE_LIST_ITEM_TEMPLATE
        % (each_index, each_number, each_url)
        for each_index, (each_number, each_url) in enumerate(
            zip(all_child_pr_numbers, all_child_pr_urls, strict=True),
            start=1,
        )
    ]
    return NEWLINE.join(
        [
            SUPERSEDE_HEADING,
            "",
            SUPERSEDE_INTRO,
            "",
            f"{SUPERSEDE_MERGE_ORDER_LABEL} {merge_order}",
            "",
            *all_list_lines,
            "",
        ]
    )


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
    all_child_pr_numbers = collect_pr_numbers_from_urls(all_child_pr_urls)
    if skip_reason is not None:
        return _skipped_payload(all_child_pr_numbers, skip_reason)

    working_directory = str(repo_root) if repo_root is not None else None
    if _is_already_superseded(
        source_pr_number=source_pr_number,
        repo=repo,
        working_directory=working_directory,
    ):
        return _skipped_payload(all_child_pr_numbers, SUPERSEDE_SKIP_ALREADY_DONE)

    comment_body = build_supersede_comment_body(
        all_child_pr_numbers=all_child_pr_numbers,
        all_child_pr_urls=all_child_pr_urls,
    )
    body_path = write_markdown_body_file(comment_body)
    run_gh_pr_comment(
        pr_number=source_pr_number,
        body_path=body_path,
        repo=repo,
        working_directory=working_directory,
        error_template=ERROR_SUPERSEDE_COMMENT_FAILED,
    )
    _run_gh_close(
        source_pr_number=source_pr_number,
        repo=repo,
        working_directory=working_directory,
    )
    return {
        PAYLOAD_KEY_COMMENTED: True,
        PAYLOAD_KEY_CLOSED: True,
        PAYLOAD_KEY_CHILD_PR_NUMBERS: all_child_pr_numbers,
        PAYLOAD_KEY_SKIPPED: False,
    }


def _skipped_payload(
    all_child_pr_numbers: list[int],
    skip_reason: str,
) -> JsonObject:
    return {
        PAYLOAD_KEY_COMMENTED: False,
        PAYLOAD_KEY_CLOSED: False,
        PAYLOAD_KEY_CHILD_PR_NUMBERS: all_child_pr_numbers,
        PAYLOAD_KEY_SKIPPED: True,
        PAYLOAD_KEY_SKIP_REASON: skip_reason,
    }


def _is_already_superseded(
    source_pr_number: int,
    repo: str | None,
    working_directory: str | None,
) -> bool:
    all_command = [
        GH_COMMAND,
        GH_PR,
        GH_VIEW,
        str(source_pr_number),
        GH_JSON,
        GH_VIEW_FIELDS,
    ]
    if repo:
        all_command.extend([GH_REPO_FLAG, repo])
    completed = subprocess.run(
        all_command,
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(ERROR_SUPERSEDE_VIEW_FAILED % (source_pr_number, detail))
    view_payload = json.loads(completed.stdout or "{}")
    if not isinstance(view_payload, dict):
        return False
    state_text = str(view_payload.get(GH_STATE_FIELD) or "")
    if state_text.upper() != GH_STATE_CLOSED:
        return False
    all_comments = view_payload.get(GH_COMMENTS_FIELD) or []
    if not isinstance(all_comments, list):
        return False
    for each_comment in all_comments:
        if not isinstance(each_comment, dict):
            continue
        body_text = str(each_comment.get(GH_COMMENT_BODY_FIELD) or "")
        if SUPERSEDE_HEADING in body_text:
            return True
    return False


def _run_gh_close(
    source_pr_number: int,
    repo: str | None,
    working_directory: str | None,
) -> None:
    all_command = [
        GH_COMMAND,
        GH_PR,
        GH_CLOSE,
        str(source_pr_number),
    ]
    if repo:
        all_command.extend([GH_REPO_FLAG, repo])
    completed = subprocess.run(
        all_command,
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(ERROR_SUPERSEDE_CLOSE_FAILED % (source_pr_number, detail))
