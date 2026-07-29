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
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from categorize_files import (
    compute_churn_by_path,
    normalize_path,
    slice_fits_review_budget,
)
from split_pr_script_types import JsonObject
from split_pr_scripts_constants.config.analyze_constants import (
    ERROR_SLICE_EXCEEDS_REVIEW_BUDGET,
    MAXIMUM_SLICE_CHANGED_LINES,
    MAXIMUM_SLICE_FILE_COUNT,
)
from split_pr_scripts_constants.config.common_constants import (
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    JSON_INDENT_SPACES,
    PAYLOAD_KEY_ERROR,
)
from split_pr_scripts_constants.config.plan_constants import (
    ALL_REQUIRED_PLAN_KEYS,
    ALL_REQUIRED_SLICE_KEYS,
    ERROR_DUPLICATE_FILES_COUNT,
    ERROR_EMPTY_SLICES_COUNT,
    ERROR_MISSING_FILES_COUNT,
    ERROR_NO_FILES,
    ERROR_NO_SLICES,
    ERROR_PLAN_INVALID_JSON,
    ERROR_PLAN_MISSING_KEY,
    ERROR_PLAN_UNREADABLE,
    ERROR_SLICE_CHANGED_LINES_TYPE,
    ERROR_SLICE_MISSING_KEY,
    ERROR_SLICE_NOT_OBJECT,
    ERROR_UNKNOWN_FILES_COUNT,
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_PROPOSED_SLICES,
    PLAN_ROOT_MUST_BE_OBJECT,
    SLICE_KEY_CHANGED_LINES,
    SLICE_KEY_FILES,
    SLICE_KEY_FILE_COUNT,
    SLICE_KEY_INDEX,
    SLICE_KEY_SLUG,
    UNKNOWN_SLICE_LABEL,
    VERIFY_KEY_COVERED_COUNT,
    VERIFY_KEY_DUPLICATE_FILES,
    VERIFY_KEY_EMPTY_SLICES,
    VERIFY_KEY_ERRORS,
    VERIFY_KEY_IS_VALID,
    VERIFY_KEY_MISSING_FILES,
    VERIFY_KEY_OVERSIZED_SLICES,
    VERIFY_KEY_SLICE_COUNT,
    VERIFY_KEY_SOURCE_COUNT,
    VERIFY_KEY_UNKNOWN_FILES,
)


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

    churn_by_path = compute_churn_by_path(all_source_records)
    inspection = _inspect_slices(all_slices, churn_by_path)
    all_errors = inspection.all_structure_errors
    all_errors.extend(inspection.all_oversized_slices)
    return _coverage_report(
        all_source_paths=set(churn_by_path),
        all_covered_paths=inspection.all_covered_paths,
        all_empty_slices=inspection.all_empty_slices,
        all_errors=all_errors,
        all_oversized_slices=inspection.all_oversized_slices,
        slice_count=len(all_slices),
    )


def _required_key_errors(plan_payload: JsonObject) -> list[str]:
    """Return one error per plan or slice key the executor indexes directly.

    ::

        _required_key_errors({"all_files": [], "proposed_slices": []})
        # flag: ["plan missing required key: source_branch", ...]

    ``execute_split`` indexes these keys without a default, so a plan that
    reaches it without them dies with a bare ``KeyError`` after branches exist.

    Args:
        plan_payload: Parsed plan dict.

    Returns:
        Human-readable error strings, empty when every key is present.
    """
    all_errors = [
        ERROR_PLAN_MISSING_KEY % each_key
        for each_key in ALL_REQUIRED_PLAN_KEYS
        if each_key not in plan_payload
    ]
    all_errors.extend(_required_slice_key_errors(plan_payload))
    return all_errors


def _required_slice_key_errors(plan_payload: JsonObject) -> list[str]:
    all_slices = plan_payload.get(PLAN_KEY_PROPOSED_SLICES)
    if not isinstance(all_slices, list):
        return []
    all_errors: list[str] = []
    for each_position, each_slice in enumerate(all_slices, start=1):
        if not isinstance(each_slice, dict):
            continue
        label = _slice_label(each_slice, fallback=str(each_position))
        all_errors.extend(
            ERROR_SLICE_MISSING_KEY % (label, each_key)
            for each_key in ALL_REQUIRED_SLICE_KEYS
            if each_key not in each_slice
        )
    return all_errors


def _slice_label(each_slice: JsonObject, fallback: str = UNKNOWN_SLICE_LABEL) -> str:
    slug = each_slice.get(SLICE_KEY_SLUG)
    if slug:
        return str(slug)
    index = each_slice.get(SLICE_KEY_INDEX)
    if index is not None:
        return str(index)
    return fallback


@dataclass
class _SliceInspection:
    """What one walk over the plan's slices collects.

    ::

        slices: [{"slug": "api", "files": ["./src/a.ts"]}, {"slug": "ui"}, 7]
        ok:   all_covered_paths     -> ["src/a.ts"]
        flag: all_empty_slices      -> ["ui"]
        flag: all_structure_errors  -> ["slice entry is not an object"]

    Attributes:
        all_covered_paths: Normalized paths the slices claim, duplicates kept.
        all_empty_slices: Labels of slices that claim no file.
        all_structure_errors: Errors about slice shape.
        all_oversized_slices: Errors about slices past the review budget.
    """

    all_covered_paths: list[str] = field(default_factory=list)
    all_empty_slices: list[str] = field(default_factory=list)
    all_structure_errors: list[str] = field(default_factory=list)
    all_oversized_slices: list[str] = field(default_factory=list)


def _inspect_slices(
    all_slices: list[object],
    churn_by_path: dict[str, int],
) -> _SliceInspection:
    inspection = _SliceInspection()
    for each_slice in all_slices:
        if not isinstance(each_slice, dict):
            inspection.all_structure_errors.append(ERROR_SLICE_NOT_OBJECT)
            continue
        _inspect_one_slice(each_slice, churn_by_path, inspection)
    return inspection


def _inspect_one_slice(
    each_slice: JsonObject,
    churn_by_path: dict[str, int],
    inspection: _SliceInspection,
) -> None:
    all_slice_files = each_slice.get(SLICE_KEY_FILES, [])
    if not isinstance(all_slice_files, list) or not all_slice_files:
        inspection.all_empty_slices.append(_slice_label(each_slice))
        return
    all_paths = [normalize_path(str(each_file)) for each_file in all_slice_files]
    inspection.all_covered_paths.extend(all_paths)
    oversized_error = _oversized_slice_error(each_slice, all_paths, churn_by_path)
    if oversized_error:
        inspection.all_oversized_slices.append(oversized_error)


def _slice_changed_lines(
    each_slice: JsonObject,
    all_paths: list[str],
    churn_by_path: dict[str, int],
) -> int:
    declared_lines = each_slice.get(SLICE_KEY_CHANGED_LINES)
    if declared_lines is None:
        return sum(churn_by_path.get(each_path, 0) for each_path in all_paths)
    if isinstance(declared_lines, bool) or not isinstance(declared_lines, (int, float)):
        raise TypeError(SLICE_KEY_CHANGED_LINES)
    return int(declared_lines)


def _oversized_slice_error(
    each_slice: JsonObject,
    all_paths: list[str],
    churn_by_path: dict[str, int],
) -> str | None:
    slug = _slice_label(each_slice)
    file_count = int(each_slice.get(SLICE_KEY_FILE_COUNT, len(all_paths)) or 0)
    if file_count <= 0:
        file_count = len(all_paths)
    try:
        changed_lines = _slice_changed_lines(each_slice, all_paths, churn_by_path)
    except TypeError:
        declared_type = type(each_slice.get(SLICE_KEY_CHANGED_LINES)).__name__
        return ERROR_SLICE_CHANGED_LINES_TYPE % (slug, declared_type)
    is_oversized_atomic = (
        len(all_paths) == 1 and changed_lines > MAXIMUM_SLICE_CHANGED_LINES
    )
    if is_oversized_atomic:
        return None
    return _review_budget_error(slug, file_count, changed_lines)


def _review_budget_error(slug: str, file_count: int, changed_lines: int) -> str | None:
    if slice_fits_review_budget(
        file_count=file_count,
        changed_lines=changed_lines,
    ):
        return None
    return ERROR_SLICE_EXCEEDS_REVIEW_BUDGET % (
        slug,
        file_count,
        MAXIMUM_SLICE_FILE_COUNT,
        changed_lines,
        MAXIMUM_SLICE_CHANGED_LINES,
    )


def _coverage_report(
    all_source_paths: set[str],
    all_covered_paths: list[str],
    all_empty_slices: list[str],
    all_errors: list[str],
    all_oversized_slices: list[str],
    slice_count: int,
) -> JsonObject:
    covered_set = set(all_covered_paths)
    all_missing = sorted(all_source_paths - covered_set)
    all_unknown = sorted(covered_set - all_source_paths)
    count_by_path = Counter(all_covered_paths)
    all_duplicates = sorted(
        each_path for each_path, each_count in count_by_path.items() if each_count > 1
    )
    if all_missing:
        all_errors.append(ERROR_MISSING_FILES_COUNT % len(all_missing))
    if all_unknown:
        all_errors.append(ERROR_UNKNOWN_FILES_COUNT % len(all_unknown))
    if all_duplicates:
        all_errors.append(ERROR_DUPLICATE_FILES_COUNT % len(all_duplicates))
    if all_empty_slices:
        all_errors.append(ERROR_EMPTY_SLICES_COUNT % len(all_empty_slices))
    return {
        VERIFY_KEY_IS_VALID: not all_errors,
        VERIFY_KEY_MISSING_FILES: all_missing,
        VERIFY_KEY_DUPLICATE_FILES: all_duplicates,
        VERIFY_KEY_UNKNOWN_FILES: all_unknown,
        VERIFY_KEY_EMPTY_SLICES: all_empty_slices,
        VERIFY_KEY_OVERSIZED_SLICES: all_oversized_slices,
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
        VERIFY_KEY_OVERSIZED_SLICES: [],
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
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({PAYLOAD_KEY_ERROR: str(error)}))
        return EXIT_CODE_FAILURE


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify split-pr plan coverage")
    parser.add_argument("--plan", required=True, help="Path to plan JSON")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
