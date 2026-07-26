"""Open one draft pull request for a slice branch and return its URL.

::

    create_draft_pr(repo_root, "feat: bell backend", story, "main",
                    "split/123/01-backend", 123, "owner/name")
    # ok: "https://github.com/owner/name/pull/10"

The body is assembled from the named heading and sentence constants, so the
wording of a slice PR lives beside the rest of the split-pr copy instead of
inside this call.
"""

from __future__ import annotations

from pathlib import Path

from split_pr_process_runner import run_gh, write_markdown_body_file
from split_pr_scripts_constants.config.common_constants import BLANK_LINE, GH_PR
from split_pr_scripts_constants.config.execute_constants import (
    DRAFT_PR_DEPENDENCIES_HEADING,
    DRAFT_PR_DEPENDENCIES_TEMPLATE,
    DRAFT_PR_SOURCE_HEADING,
    DRAFT_PR_SOURCE_TEMPLATE,
    DRAFT_PR_SUMMARY_HEADING,
    DRAFT_PR_TESTING_HEADING,
    DRAFT_PR_TESTING_NOTE,
    ERROR_PR_CREATE_FAILED,
    GH_BASE,
    GH_BODY_FILE,
    GH_CREATE,
    GH_DRAFT,
    GH_HEAD,
    GH_TITLE,
    NEWLINE,
)


def build_draft_pr_body(story: str, base_name: str, pr_number: int) -> str:
    """Return the markdown body for one slice's draft pull request.

    Args:
        story: One-line description of what the slice ships.
        base_name: Branch this slice is stacked on.
        pr_number: Source pull request the slice was excised from.

    Returns:
        Markdown with summary, split source, dependencies, and testing sections.
    """
    return NEWLINE.join(
        [
            DRAFT_PR_SUMMARY_HEADING,
            BLANK_LINE,
            story,
            BLANK_LINE,
            DRAFT_PR_SOURCE_HEADING,
            BLANK_LINE,
            DRAFT_PR_SOURCE_TEMPLATE % pr_number,
            BLANK_LINE,
            DRAFT_PR_DEPENDENCIES_HEADING,
            BLANK_LINE,
            DRAFT_PR_DEPENDENCIES_TEMPLATE % base_name,
            BLANK_LINE,
            DRAFT_PR_TESTING_HEADING,
            BLANK_LINE,
            DRAFT_PR_TESTING_NOTE,
            BLANK_LINE,
        ]
    )


def create_draft_pr(
    repo_root: Path,
    title: str,
    story: str,
    base_name: str,
    head_name: str,
    pr_number: int,
    repo: str | None,
) -> str:
    """Open a draft PR for head_name against base_name and return its URL.

    Args:
        repo_root: Directory to run gh in.
        title: Pull request title.
        story: One-line description of what the slice ships.
        base_name: Branch this slice is stacked on.
        head_name: Branch carrying the slice.
        pr_number: Source pull request the slice was excised from.
        repo: ``owner/name`` slug, or None to let gh infer the repository.

    Returns:
        The URL gh printed for the new draft pull request.

    Raises:
        RuntimeError: When ``gh pr create`` fails.
    """
    body_path = write_markdown_body_file(
        build_draft_pr_body(story=story, base_name=base_name, pr_number=pr_number)
    )
    try:
        return run_gh(
            [
                GH_PR,
                GH_CREATE,
                GH_DRAFT,
                GH_TITLE,
                title,
                GH_BODY_FILE,
                body_path,
                GH_BASE,
                base_name,
                GH_HEAD,
                head_name,
            ],
            repo=repo,
            working_directory=str(repo_root),
            error_template=ERROR_PR_CREATE_FAILED,
            all_error_context=(head_name,),
        )
    finally:
        Path(body_path).unlink(missing_ok=True)
