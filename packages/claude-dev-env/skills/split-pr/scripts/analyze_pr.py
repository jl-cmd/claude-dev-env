#!/usr/bin/env python3
"""Analyze a GitHub PR and emit a file-layer split plan JSON.

::

    python analyze_pr.py --pr 123
    {"pr_number": 123, "proposed_slices": [...], "all_files": [...]}

Uses ``gh pr view --json``. Pass ``--files-json`` in tests to skip gh.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from categorize_files import annotate_files, build_slices_from_files
from split_pr_scripts_constants.config.analyze_constants import (
    BODY_EXCERPT_MAX_LENGTH,
    BRANCH_NAME_SEPARATOR,
    BRANCH_PREFIX,
    DEFAULT_BASE_REF_NAME,
    DEFAULT_TITLE_PREFIX,
    ERROR_BELOW_SPLIT_THRESHOLD,
    ERROR_CLI_ARGUMENTS,
    ERROR_GH_FAILED,
    ERROR_GH_JSON_PARSE,
    ERROR_PR_NUMBER_REQUIRED,
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    GH_COMMAND,
    GH_FIELD_BASE_REF,
    GH_FIELD_BODY,
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
    GH_PR_JSON_FIELDS,
    GH_PR_VIEW,
    GH_REPO_FLAG,
    GH_VIEW,
    JSON_INDENT_SPACES,
    MAXIMUM_FEATURE_SLUG_LENGTH,
    MINIMUM_SPLIT_FILE_COUNT,
    PAYLOAD_KEY_ERROR,
    PLAN_BODY_EXCERPT_KEY,
    PLAN_THRESHOLD_NOTE_KEY,
    PLAN_URL_KEY,
    SLICE_INDEX_ZERO_PAD,
    SLUG_REPLACEMENT,
    TEST_HEAD_SHA,
    WARNING_BELOW_THRESHOLD,
    WARNING_OTHER_LAYER_NONEMPTY,
    WARNING_SINGLE_LAYER,
)
from split_pr_scripts_constants.config.categorize_constants import LAYER_OTHER
from split_pr_scripts_constants.config.plan_constants import (
    FILE_KEY_ADDITIONS,
    FILE_KEY_DELETIONS,
    FILE_KEY_LAYER,
    FILE_KEY_PATH,
    FILE_KEY_STATUS,
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
)

JsonObject = dict[str, object]


def slugify_feature(title: str, pr_number: int) -> str:
    """Build a short branch-safe feature slug from a PR title.

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
    all_slices = build_slices_from_files(
        all_annotated,
        feature_slug=feature_slug,
        title_prefix=title_prefix,
    )
    _assign_stack_branches(all_slices, pr_number=pr_number, base_ref=base_ref)
    all_warnings = _collect_warnings(all_annotated)
    file_count = len(all_annotated)
    threshold_note: str | None = None
    if file_count < MINIMUM_SPLIT_FILE_COUNT:
        threshold_note = ERROR_BELOW_SPLIT_THRESHOLD % (
            file_count,
            MINIMUM_SPLIT_FILE_COUNT,
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


def _file_records_from_gh(raw_files: object) -> list[JsonObject]:
    if not isinstance(raw_files, list):
        return []
    all_file_records: list[JsonObject] = []
    for each_file in raw_files:
        if not isinstance(each_file, dict):
            continue
        path = each_file.get(GH_FILE_PATH)
        if not path:
            continue
        all_file_records.append(
            {
                FILE_KEY_PATH: str(path),
                FILE_KEY_STATUS: "modified",
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
        layer_slug = str(each_slice.get("slug", f"slice-{index}"))
        branch_name = (
            f"{BRANCH_PREFIX}{BRANCH_NAME_SEPARATOR}"
            f"{pr_number}{BRANCH_NAME_SEPARATOR}"
            f"{index:0{SLICE_INDEX_ZERO_PAD}d}-{layer_slug}"
        )
        each_slice[SLICE_KEY_BRANCH] = branch_name
        each_slice[SLICE_KEY_BASE] = previous_base
        previous_base = branch_name


def _collect_warnings(all_annotated: list[JsonObject]) -> list[str]:
    all_warnings: list[str] = []
    file_count = len(all_annotated)
    if file_count < MINIMUM_SPLIT_FILE_COUNT:
        all_warnings.append(WARNING_BELOW_THRESHOLD)
    all_layers = {str(each.get(FILE_KEY_LAYER)) for each in all_annotated}
    if len(all_layers) <= 1 and file_count > 0:
        all_warnings.append(WARNING_SINGLE_LAYER)
    if any(str(each.get(FILE_KEY_LAYER)) == LAYER_OTHER for each in all_annotated):
        all_warnings.append(WARNING_OTHER_LAYER_NONEMPTY)
    return all_warnings


def _fetch_pr_payload(pr_number: int, repo: str | None) -> JsonObject:
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
        raise RuntimeError(ERROR_GH_JSON_PARSE % "root must be an object")
    return parsed_object


def _payload_from_files_json(
    files_json_path: Path,
    pr_number: int,
    title: str,
    base_ref: str,
    head_ref: str,
) -> JsonObject:
    raw_object: object = json.loads(files_json_path.read_text(encoding="utf-8"))
    if isinstance(raw_object, list):
        all_files = raw_object
    elif isinstance(raw_object, dict) and GH_FIELD_FILES in raw_object:
        all_files = raw_object[GH_FIELD_FILES]
    else:
        raise ValueError(ERROR_CLI_ARGUMENTS)
    return {
        GH_FIELD_NUMBER: pr_number,
        GH_FIELD_TITLE: title,
        GH_FIELD_BASE_REF: base_ref,
        GH_FIELD_HEAD_REF: head_ref,
        GH_FIELD_HEAD_OID: TEST_HEAD_SHA,
        GH_FIELD_FILES: all_files,
        GH_FIELD_URL: None,
        GH_FIELD_BODY: "",
    }


def main() -> int:
    """CLI entry: analyze PR and print plan JSON.

    Returns:
        Process exit code (0 success, 1 failure).

    Raises:
        Does not raise; failures print JSON error and return 1.
    """
    try:
        parsed_arguments = _parse_arguments()
        pr_number = parsed_arguments.pr
        if pr_number is None or pr_number < 1:
            raise ValueError(ERROR_PR_NUMBER_REQUIRED)
        if parsed_arguments.files_json:
            all_pr_fields = _payload_from_files_json(
                files_json_path=Path(parsed_arguments.files_json),
                pr_number=pr_number,
                title=parsed_arguments.title or f"PR {pr_number}",
                base_ref=parsed_arguments.base or DEFAULT_BASE_REF_NAME,
                head_ref=parsed_arguments.head or f"feature/pr-{pr_number}",
            )
        else:
            all_pr_fields = _fetch_pr_payload(pr_number, parsed_arguments.repo)
        plan_payload = build_plan_from_pr_payload(
            all_pr_fields,
            repo=parsed_arguments.repo,
            title_prefix=parsed_arguments.title_prefix,
        )
        indent = JSON_INDENT_SPACES if parsed_arguments.pretty else None
        print(json.dumps(plan_payload, indent=indent))
        return EXIT_CODE_SUCCESS
    except (ValueError, RuntimeError, OSError) as error:
        print(json.dumps({PAYLOAD_KEY_ERROR: str(error)}))
        return EXIT_CODE_FAILURE


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a PR for file-based split")
    parser.add_argument("--pr", type=int, required=True, help="Pull request number")
    parser.add_argument("--repo", default=None, help="owner/name for gh --repo")
    parser.add_argument(
        "--files-json",
        default=None,
        help="Offline files payload (tests); skips gh",
    )
    parser.add_argument("--title", default=None, help="Override title with --files-json")
    parser.add_argument("--base", default=None, help="Override base ref with --files-json")
    parser.add_argument("--head", default=None, help="Override head ref with --files-json")
    parser.add_argument(
        "--title-prefix",
        default=DEFAULT_TITLE_PREFIX,
        help="Conventional-commit prefix for slice titles",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
