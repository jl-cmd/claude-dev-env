#!/usr/bin/env python3
"""Analyze a GitHub PR and emit a file-layer split plan JSON.

::

    python analyze_pr.py --pr 123
    {"pr_number": 123, "proposed_slices": [...], "all_files": [...]}

Reads the pull request through ``gh``. :func:`analyze_pull_request` takes the
fetcher as an argument, so a caller supplies its own payload source.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Protocol

from categorize_files import (
    annotate_files,
    build_slices_from_files,
    build_whole_pr_slice,
    slice_fits_review_budget,
)
from split_pr_scripts_constants.config.analyze_constants import (
    BODY_EXCERPT_MAX_LENGTH,
    BRANCH_NAME_SEPARATOR,
    BRANCH_PREFIX,
    DEFAULT_BASE_REF_NAME,
    DEFAULT_TITLE_PREFIX,
    ERROR_GH_FAILED,
    ERROR_GH_FILE_COUNT_MISMATCH,
    ERROR_GH_FILE_STATUS_FAILED,
    ERROR_GH_FILE_STATUS_JSON,
    ERROR_GH_JSON_PARSE,
    ERROR_PR_NUMBER_REQUIRED,
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    GH_API,
    GH_API_FILE_FILENAME,
    GH_API_FILE_STATUS,
    GH_API_SLURP_FLAG,
    GH_COMMAND,
    GH_FIELD_BASE_REF,
    GH_FIELD_BODY,
    GH_FIELD_CHANGED_FILES,
    GH_FIELD_FILES,
    GH_FIELD_HEAD_OID,
    GH_FIELD_HEAD_REF,
    GH_FIELD_NUMBER,
    GH_FIELD_TITLE,
    GH_FIELD_URL,
    GH_FILE_ADDITIONS,
    GH_FILE_DELETIONS,
    GH_FILE_PATH,
    GH_JSON_FLAG,
    GH_PAGINATE_FLAG,
    GH_PR_FILES_DEFAULT_OWNER_REPO,
    GH_PR_FILES_ENDPOINT_TEMPLATE,
    GH_PR_JSON_FIELDS,
    GH_PR_VIEW,
    GH_REPO_FLAG,
    GH_VIEW,
    JSON_INDENT_SPACES,
    MAXIMUM_FEATURE_SLUG_LENGTH,
    MAXIMUM_SLICE_CHANGED_LINES,
    MAXIMUM_SLICE_FILE_COUNT,
    PAYLOAD_KEY_ERROR,
    PLAN_BODY_EXCERPT_KEY,
    PLAN_ROOT_MUST_BE_ARRAY,
    PLAN_ROOT_MUST_BE_OBJECT,
    PLAN_THRESHOLD_NOTE_KEY,
    PLAN_URL_KEY,
    SLICE_INDEX_ZERO_PAD,
    SLUG_REPLACEMENT,
    SPLIT_OPTIONAL_NOTE_TEMPLATE,
    WARNING_OTHER_LAYER_NONEMPTY,
    WARNING_OVERSIZED_ATOMIC_SLICE,
    WARNING_SINGLE_LAYER,
    WARNING_SPLIT_OPTIONAL,
)
from split_pr_scripts_constants.config.categorize_constants import LAYER_OTHER
from split_pr_scripts_constants.config.plan_constants import (
    FILE_KEY_ADDITIONS,
    FILE_KEY_DELETIONS,
    FILE_KEY_LAYER,
    FILE_KEY_PATH,
    FILE_KEY_STATUS,
    FILE_STATUS_MODIFIED,
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_BASE_REF,
    PLAN_KEY_FEATURE_SLUG,
    PLAN_KEY_FILE_COUNT,
    PLAN_KEY_HEAD_REF,
    PLAN_KEY_HEAD_SHA,
    PLAN_KEY_PR_NUMBER,
    PLAN_KEY_PROPOSED_SLICES,
    PLAN_KEY_REPO,
    PLAN_KEY_SOURCE_BRANCH,
    PLAN_KEY_TITLE,
    PLAN_KEY_WARNINGS,
    SLICE_KEY_BASE,
    SLICE_KEY_BRANCH,
    SLICE_KEY_INDEX,
    SLICE_KEY_OVERSIZED_ATOMIC,
    SLICE_KEY_SLUG,
)

JsonObject = dict[str, object]


class PullRequestPayloadFetcher(Protocol):
    """Reads the raw ``gh`` field payload for one pull request.

    ::

        fetch_pr_payload_through_gh(123, "owner/name")  # ok: real gh call
        lambda pr_number, repo: {}  # ok: recorded stand-in inside a test

    :func:`analyze_pull_request` takes an implementation of this protocol, so a
    caller chooses the payload source without the production path branching on
    a test flag.
    """

    def __call__(self, pr_number: int, repo: str | None) -> JsonObject:
        """Return the ``gh`` field payload for one pull request.

        Args:
            pr_number: Pull request number.
            repo: Optional ``owner/name`` scope for the lookup.

        Returns:
            Payload carrying the PR fields plus a ``files`` record list.
        """


def slugify_feature(title: str, pr_number: int) -> str:
    """Build a short branch-safe feature slug from a PR title.

    ::

        slugify_feature("feat: Add Bell!", 7)  # ok: "feat-add-bell"

    The pr-loop helper ``sanitize_branch_name`` substitutes one replacement per
    unsafe character and preserves case, so the same title yields
    ``feat--Add-Bell-``. Slice branch names need the collapsed, lowercased,
    trimmed form, so this slug stays local rather than reusing that helper.

    Args:
        title: PR title text.
        pr_number: PR number used as fallback.

    Returns:
        Lowercase hyphenated slug.
    """
    lowered = title.lower()
    cleaned = re.sub(r"[^a-z0-9]+", SLUG_REPLACEMENT, lowered).strip(SLUG_REPLACEMENT)
    if not cleaned:
        cleaned = f"pr-{pr_number}"
    return cleaned[:MAXIMUM_FEATURE_SLUG_LENGTH].strip(SLUG_REPLACEMENT)


def build_plan_from_pr_payload(
    all_pr_fields: JsonObject,
    repo: str | None,
    title_prefix: str,
) -> JsonObject:
    """Turn a gh PR payload into a split plan.

    Args:
        all_pr_fields: Output of ``gh pr view --json``.
        repo: Optional owner/name string stored on the plan.
        title_prefix: Commit/PR title prefix (default ``feat``).

    Returns:
        Plan dict with annotated files and proposed slices.
    """
    pr_number = int(all_pr_fields.get(GH_FIELD_NUMBER, 0) or 0)
    title = str(all_pr_fields.get(GH_FIELD_TITLE, f"PR {pr_number}"))
    base_ref = str(all_pr_fields.get(GH_FIELD_BASE_REF, DEFAULT_BASE_REF_NAME))
    head_ref = str(all_pr_fields.get(GH_FIELD_HEAD_REF, ""))
    head_sha = str(all_pr_fields.get(GH_FIELD_HEAD_OID, ""))
    all_file_records = _file_records_from_gh(all_pr_fields.get(GH_FIELD_FILES))
    all_annotated = annotate_files(all_file_records)
    feature_slug = slugify_feature(title, pr_number)
    file_count = len(all_annotated)
    total_changed_lines = _total_changed_lines(all_annotated)
    is_split_optional = slice_fits_review_budget(
        file_count=file_count,
        changed_lines=total_changed_lines,
    )
    all_slices = _build_slices_for_advice(
        all_annotated=all_annotated,
        is_split_optional=is_split_optional,
        feature_slug=feature_slug,
        title_prefix=title_prefix,
    )
    _assign_stack_branches(all_slices, pr_number=pr_number, base_ref=base_ref)
    all_warnings = _collect_warnings(all_annotated, all_slices, is_split_optional)
    threshold_note = (
        SPLIT_OPTIONAL_NOTE_TEMPLATE
        % (
            file_count,
            MAXIMUM_SLICE_FILE_COUNT,
            total_changed_lines,
            MAXIMUM_SLICE_CHANGED_LINES,
        )
        if is_split_optional
        else None
    )
    body_text = str(all_pr_fields.get(GH_FIELD_BODY) or "")
    return {
        PLAN_KEY_PR_NUMBER: pr_number,
        PLAN_KEY_TITLE: title,
        PLAN_KEY_BASE_REF: base_ref,
        PLAN_KEY_HEAD_REF: head_ref,
        PLAN_KEY_HEAD_SHA: head_sha,
        PLAN_KEY_SOURCE_BRANCH: head_ref,
        PLAN_KEY_REPO: repo,
        PLAN_KEY_FEATURE_SLUG: feature_slug,
        PLAN_KEY_FILE_COUNT: file_count,
        PLAN_KEY_ALL_FILES: all_annotated,
        PLAN_KEY_PROPOSED_SLICES: all_slices,
        PLAN_KEY_WARNINGS: all_warnings,
        PLAN_URL_KEY: all_pr_fields.get(GH_FIELD_URL),
        PLAN_BODY_EXCERPT_KEY: body_text[:BODY_EXCERPT_MAX_LENGTH],
        PLAN_THRESHOLD_NOTE_KEY: threshold_note,
    }


def _total_changed_lines(all_annotated: list[JsonObject]) -> int:
    return sum(
        int(each.get(FILE_KEY_ADDITIONS, 0) or 0)
        + int(each.get(FILE_KEY_DELETIONS, 0) or 0)
        for each in all_annotated
    )


def _build_slices_for_advice(
    all_annotated: list[JsonObject],
    is_split_optional: bool,
    feature_slug: str,
    title_prefix: str,
) -> list[JsonObject]:
    if is_split_optional:
        return build_whole_pr_slice(
            all_annotated,
            feature_slug=feature_slug,
            title_prefix=title_prefix,
        )
    return build_slices_from_files(
        all_annotated,
        feature_slug=feature_slug,
        title_prefix=title_prefix,
    )


def _file_records_from_gh(raw_files: object) -> list[JsonObject]:
    if not isinstance(raw_files, list):
        return []
    all_file_records: list[JsonObject] = []
    for each_file in raw_files:
        if not isinstance(each_file, dict):
            continue
        path = each_file.get(GH_API_FILE_FILENAME) or each_file.get(GH_FILE_PATH)
        if not path:
            continue
        all_file_records.append(
            {
                FILE_KEY_PATH: str(path),
                FILE_KEY_STATUS: str(
                    each_file.get(GH_API_FILE_STATUS) or FILE_STATUS_MODIFIED
                ),
                FILE_KEY_ADDITIONS: int(each_file.get(GH_FILE_ADDITIONS, 0) or 0),
                FILE_KEY_DELETIONS: int(each_file.get(GH_FILE_DELETIONS, 0) or 0),
            }
        )
    return all_file_records


def _assign_stack_branches(
    all_slices: list[JsonObject],
    pr_number: int,
    base_ref: str,
) -> None:
    previous_base = base_ref
    for each_slice in all_slices:
        index = int(each_slice[SLICE_KEY_INDEX])
        layer_slug = str(each_slice[SLICE_KEY_SLUG])
        branch_name = (
            f"{BRANCH_PREFIX}{BRANCH_NAME_SEPARATOR}"
            f"{pr_number}{BRANCH_NAME_SEPARATOR}"
            f"{index:0{SLICE_INDEX_ZERO_PAD}d}-{layer_slug}"
        )
        each_slice[SLICE_KEY_BRANCH] = branch_name
        each_slice[SLICE_KEY_BASE] = previous_base
        previous_base = branch_name


def _collect_warnings(
    all_annotated: list[JsonObject],
    all_slices: list[JsonObject],
    is_split_optional: bool,
) -> list[str]:
    all_warnings: list[str] = []
    file_count = len(all_annotated)
    if is_split_optional:
        all_warnings.append(WARNING_SPLIT_OPTIONAL)
    all_layers = {str(each.get(FILE_KEY_LAYER)) for each in all_annotated}
    if len(all_layers) <= 1 and file_count > 0:
        all_warnings.append(WARNING_SINGLE_LAYER)
    if any(str(each.get(FILE_KEY_LAYER)) == LAYER_OTHER for each in all_annotated):
        all_warnings.append(WARNING_OTHER_LAYER_NONEMPTY)
    if any(bool(each.get(SLICE_KEY_OVERSIZED_ATOMIC)) for each in all_slices):
        all_warnings.append(WARNING_OVERSIZED_ATOMIC_SLICE)
    return all_warnings


def fetch_pr_payload_through_gh(pr_number: int, repo: str | None) -> JsonObject:
    """Read one pull request's fields and complete file list through ``gh``.

    ::

        fetch_pr_payload_through_gh(123, "owner/name")
        # ok: {"number": 123, "files": [...]}

    This is the default :class:`PullRequestPayloadFetcher` implementation.

    Args:
        pr_number: Pull request number.
        repo: Optional ``owner/name`` scope for the lookup.

    Returns:
        Payload carrying the PR fields plus a ``files`` record list.

    Raises:
        RuntimeError: When gh fails, emits non-JSON, or returns a short list.
    """
    all_pr_fields = _fetch_pr_overview(pr_number, repo)
    all_pr_fields[GH_FIELD_FILES] = fetch_all_pr_files(pr_number, repo)
    assert_file_list_is_complete(all_pr_fields)
    return all_pr_fields


def _fetch_pr_overview(pr_number: int, repo: str | None) -> JsonObject:
    all_command = [
        GH_COMMAND,
        GH_PR_VIEW,
        GH_VIEW,
        str(pr_number),
        GH_JSON_FLAG,
        GH_PR_JSON_FIELDS,
    ]
    if repo:
        all_command.extend([GH_REPO_FLAG, repo])
    completed = subprocess.run(
        all_command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(ERROR_GH_FAILED % detail)
    try:
        parsed_object: object = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(ERROR_GH_JSON_PARSE % error) from error
    if not isinstance(parsed_object, dict):
        raise RuntimeError(ERROR_GH_JSON_PARSE % PLAN_ROOT_MUST_BE_OBJECT)
    return parsed_object


def fetch_all_pr_files(pr_number: int, repo: str | None) -> list[JsonObject]:
    """Read every changed file of a PR through the paginated REST endpoint.

    ::

        fetch_all_pr_files(541843, "NixOS/nixpkgs")  # ok: 672 records, not 100

    ``gh pr view --json files`` caps its array at 100 entries with no page
    marker, so an oversized PR silently loses files. The REST pull-files
    endpoint pages, and ``--paginate --slurp`` returns one JSON array per page
    for this function to flatten in one read.

    Args:
        pr_number: Pull request number.
        repo: Optional ``owner/name``; the gh repo placeholder when absent.

    Returns:
        Flattened file records carrying ``filename``, ``status``, ``additions``,
        and ``deletions``.

    Raises:
        RuntimeError: When gh fails or emits output that is not JSON.
    """
    owner_repo = repo or GH_PR_FILES_DEFAULT_OWNER_REPO
    all_command = [
        GH_COMMAND,
        GH_API,
        GH_PR_FILES_ENDPOINT_TEMPLATE % (owner_repo, pr_number),
        GH_PAGINATE_FLAG,
        GH_API_SLURP_FLAG,
    ]
    completed = subprocess.run(
        all_command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(ERROR_GH_FILE_STATUS_FAILED % detail)
    try:
        parsed_pages: object = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(ERROR_GH_FILE_STATUS_JSON % error) from error
    return _flatten_slurped_pages(parsed_pages)


def _flatten_slurped_pages(parsed_pages: object) -> list[JsonObject]:
    if not isinstance(parsed_pages, list):
        raise RuntimeError(ERROR_GH_FILE_STATUS_JSON % PLAN_ROOT_MUST_BE_ARRAY)
    all_file_records: list[JsonObject] = []
    for each_page in parsed_pages:
        if isinstance(each_page, dict):
            all_file_records.append(each_page)
            continue
        if not isinstance(each_page, list):
            raise RuntimeError(ERROR_GH_FILE_STATUS_JSON % PLAN_ROOT_MUST_BE_ARRAY)
        all_file_records.extend(
            each_entry for each_entry in each_page if isinstance(each_entry, dict)
        )
    return all_file_records


def assert_file_list_is_complete(all_pr_fields: JsonObject) -> None:
    """Raise when the fetched file list is shorter than the PR's own count.

    ::

        assert_file_list_is_complete({"changedFiles": 672, "files": [...672]})
        # ok: returns None
        assert_file_list_is_complete({"changedFiles": 672, "files": [...100]})
        # flag: RuntimeError

    A splitting tool that loses files produces a stack that verifies clean while
    dropping most of the work, so a short list fails the run outright.

    Args:
        all_pr_fields: Payload holding ``changedFiles`` and ``files``.

    Raises:
        RuntimeError: When the two counts disagree.
    """
    reported_count = all_pr_fields.get(GH_FIELD_CHANGED_FILES)
    if not isinstance(reported_count, int) or isinstance(reported_count, bool):
        return
    all_files = all_pr_fields.get(GH_FIELD_FILES)
    fetched_count = len(all_files) if isinstance(all_files, list) else 0
    if fetched_count != reported_count:
        raise RuntimeError(
            ERROR_GH_FILE_COUNT_MISMATCH % (fetched_count, reported_count)
        )


def analyze_pull_request(
    pr_number: int,
    repo: str | None,
    title_prefix: str,
    fetch_payload: PullRequestPayloadFetcher = fetch_pr_payload_through_gh,
) -> JsonObject:
    """Fetch one pull request and turn it into a split plan.

    ::

        analyze_pull_request(123, "owner/name", "feat")
        # ok: reads the live PR through gh
        analyze_pull_request(123, None, "feat", fetch_payload=stub)
        # ok: reads a recorded payload

    ``fetch_payload`` is the seam a test uses in place of the live ``gh`` call.

    Args:
        pr_number: Pull request number.
        repo: Optional ``owner/name`` stored on the plan and used for lookup.
        title_prefix: Conventional-commit prefix for slice titles.
        fetch_payload: Payload source; the ``gh``-backed reader by default.

    Returns:
        Plan dict with annotated files and proposed slices.
    """
    all_pr_fields = fetch_payload(pr_number, repo)
    return build_plan_from_pr_payload(
        all_pr_fields,
        repo=repo,
        title_prefix=title_prefix,
    )


def _plan_from_arguments(parsed_arguments: argparse.Namespace) -> JsonObject:
    pr_number = parsed_arguments.pr
    if pr_number is None or pr_number < 1:
        raise ValueError(ERROR_PR_NUMBER_REQUIRED)
    return analyze_pull_request(
        pr_number=pr_number,
        repo=parsed_arguments.repo,
        title_prefix=parsed_arguments.title_prefix,
    )


def main() -> int:
    """CLI entry: analyze PR and print plan JSON.

    Returns:
        Process exit code (0 success, 1 failure).

    Raises:
        Does not raise; failures print JSON error and return 1.
    """
    try:
        parsed_arguments = _parse_arguments()
        plan_payload = _plan_from_arguments(parsed_arguments)
        indent = JSON_INDENT_SPACES if parsed_arguments.pretty else None
        print(json.dumps(plan_payload, indent=indent))
        return EXIT_CODE_SUCCESS
    except (
        ValueError,
        RuntimeError,
        OSError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        print(json.dumps({PAYLOAD_KEY_ERROR: str(error)}))
        return EXIT_CODE_FAILURE


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a PR for file-based split")
    parser.add_argument("--pr", type=int, required=True, help="Pull request number")
    parser.add_argument("--repo", default=None, help="owner/name for gh --repo")
    parser.add_argument(
        "--title-prefix",
        default=DEFAULT_TITLE_PREFIX,
        help="Conventional-commit prefix for slice titles",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
