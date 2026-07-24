#!/usr/bin/env python3
"""Verify a split plan covers every source file exactly once.

::

    python verify_plan.py --plan plan.json
    {"is_valid": true, "missing_files": [], ...}

Exit 0 when valid; exit 1 when coverage fails or the plan is unreadable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from split_pr_scripts_constants.config.analyze_constants import (
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    PAYLOAD_KEY_ERROR,
)
from split_pr_scripts_constants.config.plan_constants import (
    ERROR_NO_FILES,
    ERROR_NO_SLICES,
    ERROR_PLAN_INVALID_JSON,
    ERROR_PLAN_MISSING_KEY,
    ERROR_PLAN_UNREADABLE,
    FILE_KEY_PATH,
    JSON_INDENT_SPACES,
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_PROPOSED_SLICES,
    PLAN_ROOT_MUST_BE_OBJECT,
    SLICE_KEY_FILES,
    SLICE_KEY_INDEX,
    SLICE_KEY_SLUG,
    VERIFY_KEY_COVERED_COUNT,
    VERIFY_KEY_DUPLICATE_FILES,
    VERIFY_KEY_EMPTY_SLICES,
    VERIFY_KEY_ERRORS,
    VERIFY_KEY_IS_VALID,
    VERIFY_KEY_MISSING_FILES,
    VERIFY_KEY_SLICE_COUNT,
    VERIFY_KEY_SOURCE_COUNT,
    VERIFY_KEY_UNKNOWN_FILES,
)

JsonObject = dict[str, object]


def load_plan(plan_path: Path) -> JsonObject:
    """Read and parse a plan JSON file.

    Args:
        plan_path: Path to the plan file.

    Returns:
        Parsed plan object.

    Raises:
        ValueError: When the file is missing or not JSON object-shaped.
    """
    try:
        raw_text = plan_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(ERROR_PLAN_UNREADABLE % error) from error
    try:
        parsed_object: object = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise ValueError(ERROR_PLAN_INVALID_JSON % error) from error
    if not isinstance(parsed_object, dict):
        raise ValueError(ERROR_PLAN_INVALID_JSON % PLAN_ROOT_MUST_BE_OBJECT)
    return parsed_object


def verify_plan(plan_payload: JsonObject) -> JsonObject:
    """Return a coverage report for one plan.

    ::

        verify_plan(plan_payload)  # is_valid true only when every path is exclusive

    Args:
        plan_payload: Parsed plan dict.

    Returns:
        Verification payload with ``is_valid`` and detail lists.
    """
    all_errors = _required_key_errors(plan_payload)
    if all_errors:
        return _invalid_payload(all_errors)

    all_source_records = plan_payload[PLAN_KEY_ALL_FILES]
    all_slices = plan_payload[PLAN_KEY_PROPOSED_SLICES]
    if not isinstance(all_source_records, list) or not all_source_records:
        return _invalid_payload([ERROR_NO_FILES])
    if not isinstance(all_slices, list) or not all_slices:
        return _invalid_payload([ERROR_NO_SLICES])

    all_source_paths = _source_paths(all_source_records)
    all_covered_paths, all_empty_slices, all_errors = _collect_slice_paths(all_slices)
    return _coverage_report(
        all_source_paths=all_source_paths,
        all_covered_paths=all_covered_paths,
        all_empty_slices=all_empty_slices,
        all_errors=all_errors,
        slice_count=len(all_slices),
    )


def _required_key_errors(plan_payload: JsonObject) -> list[str]:
    all_errors: list[str] = []
    if PLAN_KEY_ALL_FILES not in plan_payload:
        all_errors.append(ERROR_PLAN_MISSING_KEY % PLAN_KEY_ALL_FILES)
    if PLAN_KEY_PROPOSED_SLICES not in plan_payload:
        all_errors.append(ERROR_PLAN_MISSING_KEY % PLAN_KEY_PROPOSED_SLICES)
    return all_errors


def _source_paths(all_source_records: list[object]) -> set[str]:
    all_paths: set[str] = set()
    for each_record in all_source_records:
        if not isinstance(each_record, dict):
            continue
        file_path = each_record.get(FILE_KEY_PATH)
        if file_path:
            all_paths.add(str(file_path).replace("\\", "/"))
    return all_paths


def _collect_slice_paths(
    all_slices: list[object],
) -> tuple[list[str], list[str], list[str]]:
    all_covered_paths: list[str] = []
    all_empty_slices: list[str] = []
    all_errors: list[str] = []
    for each_slice in all_slices:
        if not isinstance(each_slice, dict):
            all_errors.append("slice entry is not an object")
            continue
        all_slice_files = each_slice.get(SLICE_KEY_FILES, [])
        if not isinstance(all_slice_files, list) or not all_slice_files:
            slug = str(
                each_slice.get(SLICE_KEY_SLUG, each_slice.get(SLICE_KEY_INDEX, "?"))
            )
            all_empty_slices.append(slug)
            continue
        for each_path in all_slice_files:
            all_covered_paths.append(str(each_path).replace("\\", "/"))
    return all_covered_paths, all_empty_slices, all_errors


def _coverage_report(
    all_source_paths: set[str],
    all_covered_paths: list[str],
    all_empty_slices: list[str],
    all_errors: list[str],
    slice_count: int,
) -> JsonObject:
    covered_set = set(all_covered_paths)
    all_missing = sorted(all_source_paths - covered_set)
    all_unknown = sorted(covered_set - all_source_paths)
    all_duplicates = sorted(
        {
            each_path
            for each_path in all_covered_paths
            if all_covered_paths.count(each_path) > 1
        }
    )
    if all_missing:
        all_errors.append(f"missing_files:{len(all_missing)}")
    if all_unknown:
        all_errors.append(f"unknown_files:{len(all_unknown)}")
    if all_duplicates:
        all_errors.append(f"duplicate_files:{len(all_duplicates)}")
    if all_empty_slices:
        all_errors.append(f"empty_slices:{len(all_empty_slices)}")
    return {
        VERIFY_KEY_IS_VALID: not all_errors,
        VERIFY_KEY_MISSING_FILES: all_missing,
        VERIFY_KEY_DUPLICATE_FILES: all_duplicates,
        VERIFY_KEY_UNKNOWN_FILES: all_unknown,
        VERIFY_KEY_EMPTY_SLICES: all_empty_slices,
        VERIFY_KEY_SLICE_COUNT: slice_count,
        VERIFY_KEY_COVERED_COUNT: len(covered_set),
        VERIFY_KEY_SOURCE_COUNT: len(all_source_paths),
        VERIFY_KEY_ERRORS: all_errors,
    }


def _invalid_payload(all_errors: list[str]) -> JsonObject:
    return {
        VERIFY_KEY_IS_VALID: False,
        VERIFY_KEY_MISSING_FILES: [],
        VERIFY_KEY_DUPLICATE_FILES: [],
        VERIFY_KEY_UNKNOWN_FILES: [],
        VERIFY_KEY_EMPTY_SLICES: [],
        VERIFY_KEY_SLICE_COUNT: 0,
        VERIFY_KEY_COVERED_COUNT: 0,
        VERIFY_KEY_SOURCE_COUNT: 0,
        VERIFY_KEY_ERRORS: all_errors,
    }


def main() -> int:
    """CLI entry: verify plan file and print JSON report.

    Returns:
        Process exit code (0 valid, 1 invalid or unreadable).
    """
    try:
        parsed_arguments = _parse_arguments()
        plan_payload = load_plan(Path(parsed_arguments.plan))
        report = verify_plan(plan_payload)
        indent = JSON_INDENT_SPACES if parsed_arguments.pretty else None
        print(json.dumps(report, indent=indent))
        if report[VERIFY_KEY_IS_VALID]:
            return EXIT_CODE_SUCCESS
        return EXIT_CODE_FAILURE
    except (ValueError, OSError) as error:
        print(json.dumps({PAYLOAD_KEY_ERROR: str(error)}))
        return EXIT_CODE_FAILURE


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify split-pr plan coverage")
    parser.add_argument("--plan", required=True, help="Path to plan JSON")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
