#!/usr/bin/env python3
"""Analyze PR churn with the hand-written line metric and 200/600 gates.

::

    python analyze_pr.py --files-json files.json --pretty
    {"hand_written_lines": 200, "requires_split_analysis": true, ...}

Uses paginated ``gh api .../pulls/N/files`` unless ``--files-json`` is offline.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from categorize_files import annotate_files, sum_churn_by_class
from config.split_pr_constants import (
    CHURN_CLASS_HAND_WRITTEN,
    DEFAULT_SPLIT_HAND_WRITTEN_LINE_THRESHOLD,
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    FILE_KEY_ADDITIONS,
    FILE_KEY_CHANGED_LINES,
    FILE_KEY_CHURN_CLASS,
    FILE_KEY_DELETIONS,
    FILE_KEY_PATH,
    GH_API_SUBCOMMAND,
    GH_COMMAND,
    GH_FILE_ADDITIONS,
    GH_FILE_DELETIONS,
    GH_FILE_FILENAME,
    GH_FILE_PATH,
    GH_JSON_FLAG,
    GH_NAME_WITH_OWNER_FIELD,
    GH_PAGINATE_FLAG,
    GH_PULLS_FILES_PATH_TEMPLATE,
    GH_REPO_SUBCOMMAND,
    GH_SLURP_FLAG,
    GH_VIEW,
    JSON_INDENT_SPACES,
    PAYLOAD_KEY_ALL_FILES,
    PAYLOAD_KEY_ATOMIC_EXCEPTION,
    PAYLOAD_KEY_DEFAULT_SPLIT,
    PAYLOAD_KEY_ERROR,
    PAYLOAD_KEY_EXCLUDED_CHURN_LINES,
    PAYLOAD_KEY_FABLE_VERDICT,
    PAYLOAD_KEY_FILE_COUNT,
    PAYLOAD_KEY_HAND_WRITTEN_LINES,
    PAYLOAD_KEY_REASON,
    PAYLOAD_KEY_REQUIRES_SPLIT_ANALYSIS,
    SPLIT_ANALYSIS_HAND_WRITTEN_LINE_THRESHOLD,
    UTF8_ENCODING,
)

JsonObject = dict[str, object]


def build_analysis_from_files(
    all_file_records: list[JsonObject],
    *,
    atomic_exception_reason: str | None = None,
    fable_verdict: str | None = None,
) -> JsonObject:
    """Build the hand-written line analysis document.

    Args:
        all_file_records: Raw path/additions/deletions maps.
        atomic_exception_reason: When set at 600+, records an atomic exception.
        fable_verdict: Standing Fable verdict token required with the exception.

    Returns:
        Analysis payload with thresholds and optional atomic_exception.

    Raises:
        ValueError: When an atomic exception is set without a Fable verdict.
    """
    all_annotated = annotate_files(all_file_records)
    hand_written_lines = sum_churn_by_class(
        all_annotated, churn_class=CHURN_CLASS_HAND_WRITTEN
    )
    excluded_churn_lines = 0
    for each_record in all_annotated:
        if each_record.get(FILE_KEY_CHURN_CLASS) != CHURN_CLASS_HAND_WRITTEN:
            excluded_churn_lines += int(
                each_record.get(FILE_KEY_CHANGED_LINES, 0) or 0
            )
    file_count = len(all_annotated)
    requires_split_analysis = (
        hand_written_lines >= SPLIT_ANALYSIS_HAND_WRITTEN_LINE_THRESHOLD
    )
    default_split = hand_written_lines >= DEFAULT_SPLIT_HAND_WRITTEN_LINE_THRESHOLD
    analysis: JsonObject = {
        PAYLOAD_KEY_HAND_WRITTEN_LINES: hand_written_lines,
        PAYLOAD_KEY_EXCLUDED_CHURN_LINES: excluded_churn_lines,
        PAYLOAD_KEY_FILE_COUNT: file_count,
        PAYLOAD_KEY_REQUIRES_SPLIT_ANALYSIS: requires_split_analysis,
        PAYLOAD_KEY_DEFAULT_SPLIT: default_split,
        PAYLOAD_KEY_ALL_FILES: all_annotated,
        PAYLOAD_KEY_ATOMIC_EXCEPTION: None,
    }
    if default_split and atomic_exception_reason:
        if not fable_verdict:
            raise ValueError(
                "atomic exception at 600+ hand-written lines requires a "
                "standing Fable verdict"
            )
        analysis[PAYLOAD_KEY_ATOMIC_EXCEPTION] = {
            PAYLOAD_KEY_REASON: atomic_exception_reason,
            PAYLOAD_KEY_FABLE_VERDICT: fable_verdict,
        }
        analysis[PAYLOAD_KEY_DEFAULT_SPLIT] = False
    return analysis


def _file_records_from_gh(raw_files: object) -> list[JsonObject]:
    if not isinstance(raw_files, list):
        return []
    all_file_records: list[JsonObject] = []
    for each_file in raw_files:
        if not isinstance(each_file, dict):
            continue
        path = each_file.get(GH_FILE_PATH) or each_file.get(GH_FILE_FILENAME)
        if not path:
            continue
        all_file_records.append(
            {
                FILE_KEY_PATH: str(path),
                FILE_KEY_ADDITIONS: int(each_file.get(GH_FILE_ADDITIONS, 0) or 0),
                FILE_KEY_DELETIONS: int(each_file.get(GH_FILE_DELETIONS, 0) or 0),
            }
        )
    return all_file_records


def _flatten_paginated_file_pages(payload: object) -> list[object]:
    if not isinstance(payload, list):
        return []
    all_files: list[object] = []
    for each_page in payload:
        if isinstance(each_page, list):
            all_files.extend(each_page)
        elif isinstance(each_page, dict):
            all_files.append(each_page)
    return all_files


def _load_files_json(files_json_path: Path) -> list[JsonObject]:
    payload = json.loads(files_json_path.read_text(encoding=UTF8_ENCODING))
    if not isinstance(payload, list):
        raise ValueError("files-json must be a JSON array")
    return _file_records_from_gh(payload)


def _resolve_repo_name(repo: str | None) -> str:
    if repo:
        return repo
    completed = subprocess.run(
        [
            GH_COMMAND,
            GH_REPO_SUBCOMMAND,
            GH_VIEW,
            GH_JSON_FLAG,
            GH_NAME_WITH_OWNER_FIELD,
        ],
        capture_output=True,
        text=True,
        check=False,
        encoding=UTF8_ENCODING,
    )
    if completed.returncode != EXIT_CODE_SUCCESS:
        raise RuntimeError(
            completed.stderr.strip()
            or "gh repo view failed; pass --repo owner/name"
        )
    payload = json.loads(completed.stdout)
    name_with_owner = payload.get(GH_NAME_WITH_OWNER_FIELD)
    if not name_with_owner:
        raise RuntimeError("gh repo view returned no nameWithOwner; pass --repo")
    return str(name_with_owner)


def _fetch_pr_files(pr_number: int, repo: str | None) -> list[JsonObject]:
    resolved_repo = _resolve_repo_name(repo)
    api_path = GH_PULLS_FILES_PATH_TEMPLATE.format(
        repo=resolved_repo,
        pr_number=pr_number,
    )
    all_command = [
        GH_COMMAND,
        GH_API_SUBCOMMAND,
        api_path,
        GH_PAGINATE_FLAG,
        GH_SLURP_FLAG,
    ]
    completed = subprocess.run(
        all_command,
        capture_output=True,
        text=True,
        check=False,
        encoding=UTF8_ENCODING,
    )
    if completed.returncode != EXIT_CODE_SUCCESS:
        raise RuntimeError(completed.stderr.strip() or "gh api pulls files failed")
    payload = json.loads(completed.stdout)
    return _file_records_from_gh(_flatten_paginated_file_pages(payload))


def _analysis_for_cli(
    all_file_records: list[JsonObject],
    exception_reason: str | None,
    standing_verdict: str | None,
) -> JsonObject:
    """Map CLI flag values onto the analysis builder kwargs."""
    return build_analysis_from_files(
        all_file_records,
        atomic_exception_reason=exception_reason,
        fable_verdict=standing_verdict,
    )


def main() -> int:
    """CLI entry: emit analysis JSON to stdout.

    Returns:
        Process exit code.

    Raises:
        Does not raise; converts analysis failures into a JSON error payload.
    """
    parser = argparse.ArgumentParser(description="Hand-written line PR analyzer")
    parser.add_argument("--pr", type=int, default=0, help="PR number for gh fetch")
    parser.add_argument("--repo", default=None, help="owner/name for gh")
    parser.add_argument(
        "--files-json",
        type=Path,
        default=None,
        help="Offline files payload (tests); skips gh",
    )
    parser.add_argument(
        "--atomic-exception-reason",
        default=None,
        help="Unsplittable reason when keeping one PR at 600+",
    )
    parser.add_argument(
        "--fable-verdict",
        default=None,
        help="Standing Fable verdict token for the atomic exception",
    )
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output")
    parsed = parser.parse_args()
    try:
        if parsed.files_json is not None:
            all_file_records = _load_files_json(parsed.files_json)
        elif parsed.pr > 0:
            all_file_records = _fetch_pr_files(parsed.pr, parsed.repo)
        else:
            raise ValueError("provide --pr or --files-json")
        analysis = _analysis_for_cli(
            all_file_records,
            parsed.atomic_exception_reason,
            parsed.fable_verdict,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(
            json.dumps({PAYLOAD_KEY_ERROR: str(error)}),
            file=sys.stdout,
        )
        return EXIT_CODE_FAILURE
    indent = JSON_INDENT_SPACES if parsed.pretty else None
    print(json.dumps(analysis, indent=indent))
    return EXIT_CODE_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
