#!/usr/bin/env python3
"""Apply discovery labels on every PR in a stacked split.

::

    apply_stack_labels(
        source_pr_number=99,
        all_child_pr_urls=["https://github.com/o/r/pull/10", "..."],
        planned_slice_count=2,
        should_create_prs=True,
    )
    {"labeled": true, "labels": ["split-pr", "split-stack:99"], "skipped": false}

Labels are a filter layer (``split-pr``, ``split-stack:<source>``). Merge order
and family tree stay on comments and stacked bases.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from split_pr_scripts_constants.config.execute_constants import (
    ERROR_STACK_LABEL_APPLY_FAILED,
    ERROR_STACK_LABEL_ENSURE_FAILED,
    GH_ADD_LABEL,
    GH_COMMAND,
    GH_EDIT,
    GH_LABEL,
    GH_LABEL_COLOR,
    GH_LABEL_CREATE,
    GH_LABEL_DESCRIPTION,
    GH_LABEL_FORCE,
    GH_PR,
    GH_REPO_FLAG,
    LABEL_SPLIT_PR,
    LABEL_SPLIT_PR_COLOR,
    LABEL_SPLIT_PR_DESCRIPTION,
    LABEL_STACK_COLOR,
    LABEL_STACK_DESCRIPTION_TEMPLATE,
    LABEL_STACK_PREFIX,
    PAYLOAD_KEY_CHILD_PR_NUMBERS,
    PAYLOAD_KEY_LABELED,
    PAYLOAD_KEY_LABELED_PR_NUMBERS,
    PAYLOAD_KEY_LABELS,
    PAYLOAD_KEY_SKIPPED,
    PAYLOAD_KEY_SKIP_REASON,
    STACK_LABELS_SKIP_CREATE_PRS_OFF,
    STACK_LABELS_SKIP_NO_CHILD_URLS,
    STACK_LABELS_SKIP_PARTIAL,
)
from supersede_source_pr import collect_pr_numbers_from_urls

JsonObject = dict[str, object]


def build_stack_label_names(source_pr_number: int) -> list[str]:
    """Return the fixed discovery labels for one split source.

    Args:
        source_pr_number: Original PR that was file-split.

    Returns:
        ``split-pr`` and ``split-stack:<source>`` in that order.
    """
    return [LABEL_SPLIT_PR, f"{LABEL_STACK_PREFIX}{source_pr_number}"]


def resolve_stack_labels_skip_reason(
    planned_slice_count: int,
    all_child_pr_urls: list[str],
    should_create_prs: bool,
) -> str | None:
    """Return a skip reason when stack labels must not run.

    Args:
        planned_slice_count: Number of slices in the verified plan.
        all_child_pr_urls: Draft PR URLs created this execute.
        should_create_prs: Whether execute opened draft PRs on GitHub.

    Returns:
        Stable skip-reason string, or None when labels may proceed.
    """
    if not should_create_prs:
        return STACK_LABELS_SKIP_CREATE_PRS_OFF
    if not all_child_pr_urls:
        return STACK_LABELS_SKIP_NO_CHILD_URLS
    if len(all_child_pr_urls) < planned_slice_count:
        return STACK_LABELS_SKIP_PARTIAL
    return None


def apply_stack_labels(
    source_pr_number: int,
    all_child_pr_urls: list[str],
    planned_slice_count: int,
    should_create_prs: bool,
    repo: str | None = None,
    repo_root: Path | None = None,
) -> JsonObject:
    """Ensure labels exist and apply them to source + every child PR.

    Args:
        source_pr_number: Original PR that was split.
        all_child_pr_urls: Ordered draft PR URLs for every planned slice.
        planned_slice_count: Slice count from the verified plan.
        should_create_prs: True when this execute opened draft PRs.
        repo: Optional ``owner/name`` for ``gh --repo``.
        repo_root: Working directory for ``gh``.

    Returns:
        Payload with ``labeled``, ``labeled_pr_numbers``, ``labels``, and skip
        metadata.

    Raises:
        RuntimeError: When label create or ``gh pr edit`` fails.
    """
    skip_reason = resolve_stack_labels_skip_reason(
        planned_slice_count=planned_slice_count,
        all_child_pr_urls=all_child_pr_urls,
        should_create_prs=should_create_prs,
    )
    all_child_pr_numbers = collect_pr_numbers_from_urls(all_child_pr_urls)
    all_label_names = build_stack_label_names(source_pr_number)
    if skip_reason is not None:
        return {
            PAYLOAD_KEY_LABELED: False,
            PAYLOAD_KEY_LABELED_PR_NUMBERS: [],
            PAYLOAD_KEY_LABELS: all_label_names,
            PAYLOAD_KEY_CHILD_PR_NUMBERS: all_child_pr_numbers,
            PAYLOAD_KEY_SKIPPED: True,
            PAYLOAD_KEY_SKIP_REASON: skip_reason,
        }

    working_directory = str(repo_root) if repo_root is not None else None
    _ensure_stack_labels_exist(
        source_pr_number=source_pr_number,
        all_label_names=all_label_names,
        repo=repo,
        working_directory=working_directory,
    )
    all_targets = [source_pr_number, *all_child_pr_numbers]
    all_labeled: list[int] = []
    for each_number in all_targets:
        _add_labels_to_pr(
            pr_number=each_number,
            all_label_names=all_label_names,
            repo=repo,
            working_directory=working_directory,
        )
        all_labeled.append(each_number)

    return {
        PAYLOAD_KEY_LABELED: True,
        PAYLOAD_KEY_LABELED_PR_NUMBERS: all_labeled,
        PAYLOAD_KEY_LABELS: all_label_names,
        PAYLOAD_KEY_CHILD_PR_NUMBERS: all_child_pr_numbers,
        PAYLOAD_KEY_SKIPPED: False,
    }


def _ensure_stack_labels_exist(
    source_pr_number: int,
    all_label_names: list[str],
    repo: str | None,
    working_directory: str | None,
) -> None:
    for each_label_name in all_label_names:
        if each_label_name == LABEL_SPLIT_PR:
            color = LABEL_SPLIT_PR_COLOR
            description = LABEL_SPLIT_PR_DESCRIPTION
        else:
            color = LABEL_STACK_COLOR
            description = LABEL_STACK_DESCRIPTION_TEMPLATE % source_pr_number
        all_command = [
            GH_COMMAND,
            GH_LABEL,
            GH_LABEL_CREATE,
            each_label_name,
            GH_LABEL_FORCE,
            GH_LABEL_COLOR,
            color,
            GH_LABEL_DESCRIPTION,
            description,
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
            raise RuntimeError(
                ERROR_STACK_LABEL_ENSURE_FAILED % (each_label_name, detail)
            )


def _add_labels_to_pr(
    pr_number: int,
    all_label_names: list[str],
    repo: str | None,
    working_directory: str | None,
) -> None:
    all_command = [
        GH_COMMAND,
        GH_PR,
        GH_EDIT,
        str(pr_number),
    ]
    for each_label_name in all_label_names:
        all_command.extend([GH_ADD_LABEL, each_label_name])
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
        raise RuntimeError(ERROR_STACK_LABEL_APPLY_FAILED % (pr_number, detail))
