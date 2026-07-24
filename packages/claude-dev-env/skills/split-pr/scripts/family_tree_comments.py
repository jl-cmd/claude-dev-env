#!/usr/bin/env python3
"""Post the full stack family tree as a comment on every child PR.

::

    post_family_tree_comments(
        source_pr_number=99,
        all_child_pr_urls=["https://github.com/o/r/pull/10", "..."],
        planned_slice_count=2,
        should_create_prs=True,
    )
    {"commented": true, "commented_pr_numbers": [10, 11], "skipped": false}

Runs after every planned slice has a draft URL. Each PR gets the same merge
order and linked list; the current PR is marked ``this PR``. Uses
``gh pr comment --body-file``.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from split_pr_scripts_constants.config.execute_constants import (
    ERROR_FAMILY_TREE_COMMENT_FAILED,
    FAMILY_TREE_HEADING,
    FAMILY_TREE_LIST_ITEM_TEMPLATE,
    FAMILY_TREE_LIST_ITEM_THIS_TEMPLATE,
    FAMILY_TREE_MERGE_HINT,
    FAMILY_TREE_MERGE_ORDER_LABEL,
    FAMILY_TREE_POSITION_TEMPLATE,
    FAMILY_TREE_SKIP_CREATE_PRS_OFF,
    FAMILY_TREE_SKIP_NO_CHILD_URLS,
    FAMILY_TREE_SKIP_PARTIAL,
    FAMILY_TREE_SOURCE_LABEL,
    GH_BODY_FILE,
    GH_COMMAND,
    GH_COMMENT,
    GH_PR,
    GH_REPO_FLAG,
    MARKDOWN_BODY_SUFFIX,
    NEWLINE,
    PAYLOAD_KEY_CHILD_PR_NUMBERS,
    PAYLOAD_KEY_COMMENTED,
    PAYLOAD_KEY_COMMENTED_PR_NUMBERS,
    PAYLOAD_KEY_SKIPPED,
    PAYLOAD_KEY_SKIP_REASON,
    SUPERSEDE_MERGE_ORDER_SEPARATOR,
    SUPERSEDE_PR_HASH_PREFIX,
)
from supersede_source_pr import collect_pr_numbers_from_urls

JsonObject = dict[str, object]


def build_family_tree_comment_body(
    source_pr_number: int,
    all_child_pr_numbers: list[int],
    all_child_pr_urls: list[str],
    this_pr_number: int,
) -> str:
    """Build family-tree markdown for one child PR in the stack.

    Args:
        source_pr_number: Original PR that was split.
        all_child_pr_numbers: Ordered child PR numbers for the full stack.
        all_child_pr_urls: Ordered permanent URLs matching those numbers.
        this_pr_number: PR receiving the comment (marked in the list).

    Returns:
        Markdown with source, merge order, full linked list, and position.
    """
    merge_order = SUPERSEDE_MERGE_ORDER_SEPARATOR.join(
        f"{SUPERSEDE_PR_HASH_PREFIX}{each_number}"
        for each_number in all_child_pr_numbers
    )
    all_list_lines: list[str] = []
    this_position = 1
    for each_index, (each_number, each_url) in enumerate(
        zip(all_child_pr_numbers, all_child_pr_urls, strict=True),
        start=1,
    ):
        if each_number == this_pr_number:
            this_position = each_index
            all_list_lines.append(
                FAMILY_TREE_LIST_ITEM_THIS_TEMPLATE
                % (each_index, each_number, each_url)
            )
        else:
            all_list_lines.append(
                FAMILY_TREE_LIST_ITEM_TEMPLATE % (each_index, each_number, each_url)
            )
    position_line = FAMILY_TREE_POSITION_TEMPLATE % (
        this_pr_number,
        this_position,
        len(all_child_pr_numbers),
    )
    return NEWLINE.join(
        [
            FAMILY_TREE_HEADING,
            "",
            f"{FAMILY_TREE_SOURCE_LABEL} #{source_pr_number}",
            "",
            f"{FAMILY_TREE_MERGE_ORDER_LABEL} {merge_order}",
            "",
            *all_list_lines,
            "",
            position_line,
            FAMILY_TREE_MERGE_HINT,
            "",
        ]
    )


def resolve_family_tree_skip_reason(
    planned_slice_count: int,
    all_child_pr_urls: list[str],
    should_create_prs: bool,
) -> str | None:
    """Return a skip reason when family-tree comments must not run.

    Args:
        planned_slice_count: Number of slices in the verified plan.
        all_child_pr_urls: Draft PR URLs created this execute.
        should_create_prs: Whether execute opened draft PRs on GitHub.

    Returns:
        Stable skip-reason string, or None when comments may proceed.
    """
    if not should_create_prs:
        return FAMILY_TREE_SKIP_CREATE_PRS_OFF
    if not all_child_pr_urls:
        return FAMILY_TREE_SKIP_NO_CHILD_URLS
    if len(all_child_pr_urls) < planned_slice_count:
        return FAMILY_TREE_SKIP_PARTIAL
    return None


def post_family_tree_comments(
    source_pr_number: int,
    all_child_pr_urls: list[str],
    planned_slice_count: int,
    should_create_prs: bool,
    repo: str | None = None,
    repo_root: Path | None = None,
) -> JsonObject:
    """Comment the full linked stack on every child PR.

    Args:
        source_pr_number: Original PR that was split.
        all_child_pr_urls: Ordered draft PR URLs for every planned slice.
        planned_slice_count: Slice count from the verified plan.
        should_create_prs: True when this execute opened draft PRs.
        repo: Optional ``owner/name`` for ``gh --repo``.
        repo_root: Working directory for ``gh``.

    Returns:
        Payload with ``commented``, ``commented_pr_numbers``, and skip metadata.

    Raises:
        RuntimeError: When a ``gh pr comment`` call fails.
    """
    skip_reason = resolve_family_tree_skip_reason(
        planned_slice_count=planned_slice_count,
        all_child_pr_urls=all_child_pr_urls,
        should_create_prs=should_create_prs,
    )
    all_child_pr_numbers = collect_pr_numbers_from_urls(all_child_pr_urls)
    if skip_reason is not None:
        return {
            PAYLOAD_KEY_COMMENTED: False,
            PAYLOAD_KEY_COMMENTED_PR_NUMBERS: [],
            PAYLOAD_KEY_CHILD_PR_NUMBERS: all_child_pr_numbers,
            PAYLOAD_KEY_SKIPPED: True,
            PAYLOAD_KEY_SKIP_REASON: skip_reason,
        }

    working_directory = str(repo_root) if repo_root is not None else None
    all_commented: list[int] = []
    for each_number in all_child_pr_numbers:
        comment_body = build_family_tree_comment_body(
            source_pr_number=source_pr_number,
            all_child_pr_numbers=all_child_pr_numbers,
            all_child_pr_urls=all_child_pr_urls,
            this_pr_number=each_number,
        )
        body_path = _write_body_file(comment_body)
        _run_gh_comment(
            pr_number=each_number,
            body_path=body_path,
            repo=repo,
            working_directory=working_directory,
        )
        all_commented.append(each_number)

    return {
        PAYLOAD_KEY_COMMENTED: True,
        PAYLOAD_KEY_COMMENTED_PR_NUMBERS: all_commented,
        PAYLOAD_KEY_CHILD_PR_NUMBERS: all_child_pr_numbers,
        PAYLOAD_KEY_SKIPPED: False,
    }


def _write_body_file(comment_body: str) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=MARKDOWN_BODY_SUFFIX,
        delete=False,
    ) as body_file:
        body_file.write(comment_body)
        return body_file.name


def _run_gh_comment(
    pr_number: int,
    body_path: str,
    repo: str | None,
    working_directory: str | None,
) -> None:
    all_command = [
        GH_COMMAND,
        GH_PR,
        GH_COMMENT,
        str(pr_number),
        GH_BODY_FILE,
        body_path,
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
        raise RuntimeError(ERROR_FAMILY_TREE_COMMENT_FAILED % (pr_number, detail))
