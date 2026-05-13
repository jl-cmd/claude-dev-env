"""Canonical path resolution for pr-loop skills (bugteam, qbug, findbugs, fixbugs).

Single source of truth for all path patterns — when a path changes, only this
file is edited. Pure functions with no side effects.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from config.path_resolver_constants import (
    DIFF_PATCH_TEMPLATE,
    FIX_OUTCOME_XML_TEMPLATE,
    MULTI_PR_SLUG_TEMPLATE,
    OUTCOME_XML_TEMPLATE,
    PER_PR_WORKSPACE_TEMPLATE,
    RUN_NAME_TEMPLATE_MULTI,
    RUN_NAME_TEMPLATE_SINGLE,
    SLUGIFY_REPLACEMENT,
    SLUGIFY_SAFE_CHARS,
    WORKTREE_DIRNAME,
)


def sanitize_branch_name(head_branch: str) -> str:
    """Replace filesystem-unsafe characters in a git branch name.

    Args:
        head_branch: Raw git branch name (e.g. 'feat/my-branch').

    Returns:
        Sanitized string safe for use in directory names.
    """
    return SLUGIFY_SAFE_CHARS.sub(SLUGIFY_REPLACEMENT, head_branch)


def build_run_name(pr_number: int, head_branch: str, *, is_multi_pr: bool) -> str:
    """Build the run_name directory token for a single or multi-PR run.

    Args:
        pr_number: Pull request number.
        head_branch: Head branch ref (used for multi-PR naming).
        is_multi_pr: True when the run spans multiple PRs.

    Returns:
        Run name string (e.g. 'bugteam-pr-422' or 'bugteam-feat-my-branch').
    """
    if is_multi_pr:
        return RUN_NAME_TEMPLATE_MULTI.format(
            sanitized_branch=sanitize_branch_name(head_branch),
        )
    return RUN_NAME_TEMPLATE_SINGLE.format(number=pr_number)


def resolve_run_temp_dir(run_name: str) -> Path:
    """Resolve the temporary directory for a given run name.

    Args:
        run_name: Run name token (from build_run_name).

    Returns:
        Absolute path to the run's temp directory.
    """
    return Path(tempfile.gettempdir()) / run_name


def slugify_pr_identity(owner: str, repo: str, pr_number: int) -> str:
    """Generate a slugified identity token for a PR.

    Used as a subdirectory name under the run temp dir in multi-PR scenarios.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        pr_number: Pull request number.

    Returns:
        Slugified token (e.g. 'jl-cmd-claude-code-config-pr-422').
    """
    return MULTI_PR_SLUG_TEMPLATE.format(owner=owner, repo=repo, number=pr_number)


def per_pr_workspace(
    run_temp_dir: Path, owner: str, repo: str, pr_number: int
) -> dict[str, object]:
    """Build the per-PR workspace paths dict.

    Args:
        run_temp_dir: Run temp directory (from resolve_run_temp_dir).
        owner: GitHub repository owner.
        repo: GitHub repository name.
        pr_number: Pull request number.

    Returns:
        Dict with keys:
          - worktree: Path to the git worktree checkout
          - diff_patch_template: str template with {loop} placeholder
          - outcome_xml_template: str template with {number} and {loop} placeholders
          - fix_outcome_xml_template: str template with {number} and {loop} placeholders
    """
    pr_workspace_dir = run_temp_dir / PER_PR_WORKSPACE_TEMPLATE.format(number=pr_number)
    slug = slugify_pr_identity(owner, repo, pr_number)
    return {
        "worktree": pr_workspace_dir / WORKTREE_DIRNAME,
        "diff_patch_template": str(pr_workspace_dir / slug / DIFF_PATCH_TEMPLATE),
        "outcome_xml_template": OUTCOME_XML_TEMPLATE,
        "fix_outcome_xml_template": FIX_OUTCOME_XML_TEMPLATE,
    }


def outcome_xml_path(worktree_path: Path, pr_number: int, loop_number: int) -> Path:
    """Construct the canonical path for an AUDIT outcome XML file.

    Args:
        worktree_path: Path to the git worktree (from per_pr_workspace).
        pr_number: Pull request number.
        loop_number: Current loop iteration.

    Returns:
        Absolute path (e.g. '<worktree>/.bugteam-pr422-loop3.outcomes.xml').
    """
    return worktree_path / OUTCOME_XML_TEMPLATE.format(
        number=pr_number, loop=loop_number
    )


def fix_outcome_xml_path(worktree_path: Path, pr_number: int, loop_number: int) -> Path:
    """Construct the canonical path for a FIX outcome XML file.

    Args:
        worktree_path: Path to the git worktree (from per_pr_workspace).
        pr_number: Pull request number.
        loop_number: Current loop iteration.

    Returns:
        Absolute path (e.g. '<worktree>/.bugteam-pr422-loop3.fix-outcomes.xml').
    """
    return worktree_path / FIX_OUTCOME_XML_TEMPLATE.format(
        number=pr_number, loop=loop_number
    )


def diff_patch_path(
    run_temp_dir: Path,
    owner: str,
    repo: str,
    pr_number: int,
    loop_number: int,
) -> Path:
    """Construct the path for a diff/patch file.

    Args:
        run_temp_dir: Run temp directory (from resolve_run_temp_dir).
        owner: GitHub repository owner.
        repo: GitHub repository name.
        pr_number: Pull request number.
        loop_number: Current loop iteration.

    Returns:
        Absolute path (e.g. '<run_temp>/jl-cmd-claude-code-config-pr-422/loop-3.patch').
    """
    slug = slugify_pr_identity(owner, repo, pr_number)
    filename = DIFF_PATCH_TEMPLATE.format(loop=loop_number)
    return run_temp_dir / slug / filename
