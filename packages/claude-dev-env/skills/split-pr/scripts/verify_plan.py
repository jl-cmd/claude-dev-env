#!/usr/bin/env python3
"""Validate a vertical split plan for coverage, uniqueness, and test co-location.

::

    python verify_plan.py --plan plan.json --pretty
    {"is_valid": true, "violations": []}

Rejects plans that isolate tests from related behavior, duplicate paths, or
omit paths from every slice.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config.split_pr_constants import (
    ALL_TEST_PATH_MARKERS,
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    JSON_INDENT_SPACES,
    PAYLOAD_KEY_ERROR,
    PLAN_KEY_IS_PREPARATORY_REFACTOR,
    PLAN_KEY_IS_VALID,
    PLAN_KEY_PATHS,
    PLAN_KEY_SLICES,
    PLAN_KEY_STORY,
    PLAN_KEY_VIOLATIONS,
    UTF8_ENCODING,
    VIOLATION_DUPLICATE_PATH,
    VIOLATION_EMPTY_STORY,
    VIOLATION_MISSING_PATH,
    VIOLATION_TEST_WITHOUT_BEHAVIOR,
)

JsonObject = dict[str, object]


def is_test_path(file_path: str) -> bool:
    """Return whether ``file_path`` looks like a test module path.

    Args:
        file_path: Repository-relative path.

    Returns:
        True when the path matches common test naming layouts.
    """
    normalized = file_path.replace("\\", "/").lower()
    basename = Path(normalized).name
    if basename.startswith("test_") or basename.endswith("_test.py"):
        return True
    for each_marker in ALL_TEST_PATH_MARKERS:
        if each_marker.replace("\\", "/") in normalized:
            return True
    return False


def related_behavior_stem(test_path: str) -> str | None:
    """Guess the production stem a test path pairs with, when name-matched.

    Args:
        test_path: Repository-relative test path.

    Returns:
        Stem without ``test_`` prefix / ``_test`` suffix, or None.
    """
    basename = Path(test_path.replace("\\", "/")).stem
    if basename.startswith("test_"):
        return basename[len("test_") :]
    if basename.endswith("_test"):
        return basename[: -len("_test")]
    return None


def _dedupe_violations(all_violations: list[str]) -> list[str]:
    all_unique: list[str] = []
    for each_violation in all_violations:
        if each_violation not in all_unique:
            all_unique.append(each_violation)
    return all_unique


def _collect_slice_path_violations(each_slice: object) -> list[str]:
    all_violations: list[str] = []
    if not isinstance(each_slice, dict):
        return ["slice_not_object"]
    story = str(each_slice.get(PLAN_KEY_STORY, "") or "").strip()
    if not story:
        all_violations.append(VIOLATION_EMPTY_STORY)
    all_paths = each_slice.get(PLAN_KEY_PATHS, [])
    if not isinstance(all_paths, list):
        all_violations.append("slice_paths_not_list")
        return all_violations
    is_preparatory = bool(each_slice.get(PLAN_KEY_IS_PREPARATORY_REFACTOR, False))
    all_slice_paths = [str(each) for each in all_paths]
    all_test_paths = [each for each in all_slice_paths if is_test_path(each)]
    all_behavior_paths = [each for each in all_slice_paths if not is_test_path(each)]
    if all_test_paths and not all_behavior_paths and not is_preparatory:
        all_violations.append(VIOLATION_TEST_WITHOUT_BEHAVIOR)
    return all_violations


def _count_path_owners(
    all_slices: list[object],
    all_changed_paths: list[str],
) -> dict[str, int]:
    path_owner_count: dict[str, int] = {each: 0 for each in all_changed_paths}
    for each_slice in all_slices:
        if not isinstance(each_slice, dict):
            continue
        all_paths = each_slice.get(PLAN_KEY_PATHS, [])
        if not isinstance(all_paths, list):
            continue
        for each_path in all_paths:
            path_text = str(each_path)
            path_owner_count[path_text] = path_owner_count.get(path_text, 0) + 1
    return path_owner_count


def _ownership_violations(all_path_owner_counts: dict[str, int]) -> list[str]:
    all_violations: list[str] = []
    for each_path, each_count in all_path_owner_counts.items():
        if each_count == 0:
            all_violations.append(f"{VIOLATION_MISSING_PATH}:{each_path}")
        if each_count > 1:
            all_violations.append(f"{VIOLATION_DUPLICATE_PATH}:{each_path}")
    return all_violations


def verify_vertical_plan(
    plan: JsonObject,
    *,
    all_changed_paths: list[str],
) -> JsonObject:
    """Validate plan slices against vertical-slice invariants.

    Args:
        plan: Object with a ``slices`` list of ``{story, paths, ...}``.
        all_changed_paths: Every path that must appear exactly once.

    Returns:
        ``{is_valid, violations}`` where violations are structured codes.
    """
    raw_slices = plan.get(PLAN_KEY_SLICES, [])
    if not isinstance(raw_slices, list):
        return {
            PLAN_KEY_IS_VALID: False,
            PLAN_KEY_VIOLATIONS: ["slices_missing_or_not_list"],
        }
    all_violations: list[str] = []
    for each_slice in raw_slices:
        all_violations.extend(_collect_slice_path_violations(each_slice))
    path_owner_count = _count_path_owners(raw_slices, all_changed_paths)
    all_violations.extend(_ownership_violations(path_owner_count))
    all_unique = _dedupe_violations(all_violations)
    return {
        PLAN_KEY_IS_VALID: len(all_unique) == 0,
        PLAN_KEY_VIOLATIONS: all_unique,
    }


def main() -> int:
    """CLI entry: validate a plan JSON file.

    Returns:
        Process exit code.

    Raises:
        Does not raise; emits JSON errors on stdout.
    """
    parser = argparse.ArgumentParser(description="Verify vertical split plan")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument(
        "--changed-paths-json",
        type=Path,
        default=None,
        help="JSON array of all changed paths; defaults to union of slice paths",
    )
    parser.add_argument("--pretty", action="store_true")
    parsed = parser.parse_args()
    try:
        plan = json.loads(parsed.plan.read_text(encoding=UTF8_ENCODING))
        if not isinstance(plan, dict):
            raise ValueError("plan root must be an object")
        if parsed.changed_paths_json is not None:
            raw_paths = json.loads(
                parsed.changed_paths_json.read_text(encoding=UTF8_ENCODING)
            )
            if not isinstance(raw_paths, list):
                raise ValueError("changed-paths-json must be an array")
            all_changed_paths = [str(each) for each in raw_paths]
        else:
            all_changed_paths = []
            for each_slice in plan.get(PLAN_KEY_SLICES, []) or []:
                if isinstance(each_slice, dict):
                    for each_path in each_slice.get(PLAN_KEY_PATHS, []) or []:
                        all_changed_paths.append(str(each_path))
        verdict = verify_vertical_plan(plan, all_changed_paths=all_changed_paths)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({PAYLOAD_KEY_ERROR: str(error)}))
        return EXIT_CODE_FAILURE
    indent = JSON_INDENT_SPACES if parsed.pretty else None
    print(json.dumps(verdict, indent=indent))
    return EXIT_CODE_SUCCESS if verdict[PLAN_KEY_IS_VALID] else EXIT_CODE_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
