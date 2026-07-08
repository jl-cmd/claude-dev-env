"""Audit proof-of-work PR comments and gate gh pr ready on a passing one.

A proof comment shows the work behind a PR: the command run on real data,
the measured outcomes, the parent issue it advances, an image when the
change is visual, and the gaps the offline proof cannot cover. This module
detects proof-shaped comment bodies, audits the five parts, and blocks
``gh pr ready`` while no passing proof comment exists on the PR. Every gh
query fails open, so a tooling failure never blocks a command.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking.pr_description_body_audit import _iter_section_headers  # noqa: E402
from blocking.pr_description_pr_number import (  # noqa: E402
    _extract_pr_number_from_command,
)
from hooks_constants.pr_description_enforcer_constants import (  # noqa: E402
    BULLET_MARKER_PATTERN,
    FENCED_CODE_BLOCK_PATTERN,
    TABLE_ROW_LINE_PATTERN,
)
from hooks_constants.pr_description_proof_of_work_constants import (  # noqa: E402
    ALL_HONEST_GAP_PHRASES,
    ALL_PR_DIFF_SUBCOMMANDS,
    ALL_PR_VIEW_NUMBER_ARGUMENTS,
    ALL_PROOF_HEADING_KEYWORDS,
    ALL_VISUAL_FILE_SUFFIXES,
    COMMENT_BODY_JSON_FIELD,
    DIGIT_PATTERN,
    GH_API_SUBCOMMAND,
    GH_COMMAND_TIMEOUT_SECONDS,
    GH_EXECUTABLE,
    GH_PAGINATE_FLAG,
    GH_SLURP_FLAG,
    HEX_COLOR_ADDED_LINE_PATTERN,
    IMAGE_EMBED_PATTERN,
    ISSUE_REFERENCE_PATTERN,
    MAX_DIFF_SCAN_CHARS,
    PLAN_LINKAGE_KEYWORD_PATTERN,
    PR_COMMENTS_API_PATH_TEMPLATE,
    PR_DIFF_NAME_ONLY_FLAG,
    PR_NUMBER_JSON_FIELD,
    PR_READY_GATE_MESSAGE_TEMPLATE,
    PR_READY_INVOCATION_PATTERN,
    PR_READY_UNDO_FLAG,
    PROOF_PART_COMMAND_MESSAGE,
    PROOF_PART_HONEST_GAPS_MESSAGE,
    PROOF_PART_MEASURED_MESSAGE,
    PROOF_PART_PLAN_LINKAGE_MESSAGE,
    PROOF_PART_VISUAL_MESSAGE,
)
from hooks_constants.setup_project_paths_constants import UTF8_ENCODING  # noqa: E402

logger = logging.getLogger(__name__)


def is_pr_ready_command(command: str) -> bool:
    """Decide whether a shell command marks a PR ready for review.

    Args:
        command: The raw shell command captured by the hook.

    Returns:
        True for a ``gh pr ready`` command without ``--undo``; False for
        every other command, including the undo form that returns a PR to
        draft and any command that only mentions the phrase ``gh pr ready``
        inside a quoted argument or commit message.
    """
    if PR_READY_UNDO_FLAG in command:
        return False
    return PR_READY_INVOCATION_PATTERN.search(command) is not None


def is_proof_shaped_body(body: str) -> bool:
    """Decide whether a comment body presents itself as a proof of work.

    Args:
        body: The comment body markdown text.

    Returns:
        True when any markdown heading names proof or verification; False
        when no heading does.
    """
    for each_header in _iter_section_headers(body):
        header_lower = each_header.lower()
        if any(each_keyword in header_lower for each_keyword in ALL_PROOF_HEADING_KEYWORDS):
            return True
    return False


def audit_proof_comment_body(body: str, pr_number: int | None) -> list[str]:
    """Audit a proof-shaped comment body for the five proof parts.

    Args:
        body: The comment body markdown text.
        pr_number: The PR number named in the command, or None when the
            command targets the current branch's PR.

    Returns:
        One message per missing proof part. Empty when the body carries a
        command block, a measured-value element, a plan-linkage sentence,
        an honest-gaps statement, and (when the PR diff is visual) an
        image embed.
    """
    is_visual_change = _detect_visual_change(pr_number)
    return _missing_proof_parts(body, is_visual_change)


def evaluate_pr_ready_gate(command: str) -> str | None:
    """Decide whether a gh pr ready command may proceed.

    Args:
        command: The raw shell command captured by the hook.

    Returns:
        A denial reason stating the five-part proof standard when the PR
        carries no passing proof comment, or None when a passing proof
        comment exists or any gh query fails.
    """
    resolved_pr_number = _extract_pr_number_from_command(command)
    if resolved_pr_number is None:
        resolved_pr_number = _resolve_current_pr_number()
    if resolved_pr_number is None:
        return None
    all_comment_bodies = _fetch_pr_comment_bodies(resolved_pr_number)
    if all_comment_bodies is None:
        return None
    is_visual_change = _detect_visual_change(resolved_pr_number)
    for each_body in all_comment_bodies:
        if not is_proof_shaped_body(each_body):
            continue
        if not _missing_proof_parts(each_body, is_visual_change):
            return None
    return PR_READY_GATE_MESSAGE_TEMPLATE.format(pr_number=resolved_pr_number)


def _run_gh_command(all_gh_arguments: list[str]) -> str | None:
    """Run one gh command and return its stdout.

    Args:
        all_gh_arguments: The gh arguments after the executable name.

    Returns:
        The command stdout on a zero exit, or None when gh is missing,
        times out, or exits non-zero — the caller fails open on None.
    """
    try:
        completed_process = subprocess.run(
            [GH_EXECUTABLE, *all_gh_arguments],
            capture_output=True,
            text=True,
            encoding=UTF8_ENCODING,
            errors="replace",
            timeout=GH_COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.warning("gh command failed to run: %s", all_gh_arguments)
        return None
    if completed_process.returncode != 0:
        logger.warning("gh command exited %d: %s", completed_process.returncode, all_gh_arguments)
        return None
    return completed_process.stdout


def _resolve_current_pr_number() -> int | None:
    """Resolve the PR number of the current branch's open PR.

    Returns:
        The PR number from ``gh pr view``, or None when no PR resolves or
        gh fails.
    """
    view_stdout = _run_gh_command(list(ALL_PR_VIEW_NUMBER_ARGUMENTS))
    if view_stdout is None:
        return None
    try:
        view_record = json.loads(view_stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(view_record, dict):
        return None
    resolved_number = view_record.get(PR_NUMBER_JSON_FIELD)
    if isinstance(resolved_number, int):
        return resolved_number
    return None


def _fetch_pr_comment_bodies(pr_number: int) -> list[str] | None:
    """Read every comment body on a PR through the paginated issues API.

    The query runs ``gh api --paginate --slurp`` so every page lands in one
    JSON array of pages, and the flattening happens here after the full
    pagination rather than per page.

    Args:
        pr_number: The PR number whose comments to read.

    Returns:
        The comment bodies across all pages, or None when gh fails or the
        output is not the slurped page-array shape — the caller fails open
        on None.
    """
    comments_api_path = PR_COMMENTS_API_PATH_TEMPLATE.format(pr_number=pr_number)
    api_stdout = _run_gh_command(
        [GH_API_SUBCOMMAND, comments_api_path, GH_PAGINATE_FLAG, GH_SLURP_FLAG]
    )
    if api_stdout is None:
        return None
    try:
        all_comment_pages = json.loads(api_stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(all_comment_pages, list):
        return None
    all_comment_bodies: list[str] = []
    for each_page in all_comment_pages:
        if not isinstance(each_page, list):
            continue
        for each_comment_record in each_page:
            if isinstance(each_comment_record, dict):
                all_comment_bodies.append(str(each_comment_record.get(COMMENT_BODY_JSON_FIELD, "")))
    return all_comment_bodies


def _detect_visual_change(pr_number: int | None) -> bool:
    """Decide whether the PR diff carries visual work.

    A diff is visual when a changed file carries an image, HTML, or
    stylesheet suffix, or when an added line carries a six-digit hex color
    value.

    Args:
        pr_number: The PR number to diff, or None to diff the current
            branch's PR.

    Returns:
        True when the diff is visual; False when it is not or when any gh
        query fails — an unknowable diff never adds the visual requirement.
    """
    all_number_arguments = [str(pr_number)] if pr_number is not None else []
    name_only_stdout = _run_gh_command(
        [*ALL_PR_DIFF_SUBCOMMANDS, *all_number_arguments, PR_DIFF_NAME_ONLY_FLAG]
    )
    if name_only_stdout is None:
        return False
    for each_changed_path in name_only_stdout.splitlines():
        if Path(each_changed_path.strip()).suffix.lower() in ALL_VISUAL_FILE_SUFFIXES:
            return True
    diff_stdout = _run_gh_command([*ALL_PR_DIFF_SUBCOMMANDS, *all_number_arguments])
    if diff_stdout is None:
        return False
    return HEX_COLOR_ADDED_LINE_PATTERN.search(diff_stdout[:MAX_DIFF_SCAN_CHARS]) is not None


def _missing_proof_parts(body: str, is_visual_change: bool) -> list[str]:
    """Collect the proof parts a comment body is missing.

    Args:
        body: The comment body markdown text.
        is_visual_change: Whether the PR diff carries visual work, which
            adds the image-embed requirement.

    Returns:
        One message per missing part, in the standard's order: command
        block, measured values, plan linkage, visual element, honest gaps.
    """
    prose_without_fences = FENCED_CODE_BLOCK_PATTERN.sub("", body)
    all_missing_parts: list[str] = []
    if not _has_command_block(body):
        all_missing_parts.append(PROOF_PART_COMMAND_MESSAGE)
    if not _has_measured_value(prose_without_fences):
        all_missing_parts.append(PROOF_PART_MEASURED_MESSAGE)
    if not _has_plan_linkage(prose_without_fences):
        all_missing_parts.append(PROOF_PART_PLAN_LINKAGE_MESSAGE)
    if is_visual_change and not _has_visual_element(prose_without_fences):
        all_missing_parts.append(PROOF_PART_VISUAL_MESSAGE)
    if not _has_honest_gaps(prose_without_fences):
        all_missing_parts.append(PROOF_PART_HONEST_GAPS_MESSAGE)
    return all_missing_parts


def _has_command_block(body: str) -> bool:
    """Report whether the body carries a fenced code block with content.

    Args:
        body: The comment body markdown text.

    Returns:
        True when at least one fenced code block holds a non-empty line
        between its fence lines.
    """
    for each_fence_match in FENCED_CODE_BLOCK_PATTERN.finditer(body):
        all_inner_lines = each_fence_match.group(0).splitlines()[1:-1]
        if any(each_line.strip() for each_line in all_inner_lines):
            return True
    return False


def _has_measured_value(prose_without_fences: str) -> bool:
    """Report whether the prose carries a measured-value element.

    Args:
        prose_without_fences: The body text with fenced code blocks removed.

    Returns:
        True when a pipe-table row or a bullet line carries a digit.
    """
    for each_line in prose_without_fences.splitlines():
        if not DIGIT_PATTERN.search(each_line):
            continue
        if TABLE_ROW_LINE_PATTERN.match(each_line) or BULLET_MARKER_PATTERN.match(each_line):
            return True
    return False


def _has_plan_linkage(prose_without_fences: str) -> bool:
    """Report whether the prose links the PR to its parent plan.

    Args:
        prose_without_fences: The body text with fenced code blocks removed.

    Returns:
        True when one line carries both an issue reference (``#123``) and a
        linkage word (issue, phase, plan, parent, advances, milestone, or
        part of).
    """
    for each_line in prose_without_fences.splitlines():
        has_issue_reference = ISSUE_REFERENCE_PATTERN.search(each_line) is not None
        if has_issue_reference and PLAN_LINKAGE_KEYWORD_PATTERN.search(each_line) is not None:
            return True
    return False


def _has_visual_element(prose_without_fences: str) -> bool:
    """Report whether the prose embeds an image.

    Args:
        prose_without_fences: The body text with fenced code blocks removed.

    Returns:
        True when a markdown image embed (``![...](...)``) is present.
    """
    return IMAGE_EMBED_PATTERN.search(prose_without_fences) is not None


def _has_honest_gaps(prose_without_fences: str) -> bool:
    """Report whether the prose states what the proof cannot show.

    Args:
        prose_without_fences: The body text with fenced code blocks removed.

    Returns:
        True when the prose carries a gap phrase (gap, limitation, cannot,
        does not show, not shown, unverified, or not covered).
    """
    prose_lower = prose_without_fences.lower()
    return any(each_phrase in prose_lower for each_phrase in ALL_HONEST_GAP_PHRASES)
