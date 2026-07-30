"""Verify complete unique path coverage for a split-plan document.

::

    python verify_plan.py --plan-json plan.json
    # exit 0 when every changed path is assigned once

Fails closed on unassigned paths, duplicate assignments, empty source
commit, and non-normalized titles.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.plan_constants import (
    EXIT_CODE_SUCCESS,
    PATH_SEPARATOR,
    PLAN_KEY_ALL_CHANGED_PATHS,
    PLAN_KEY_ALL_SLICES,
    PLAN_KEY_SOURCE_COMMIT,
    SLICE_KEY_ALL_PATHS,
    UTF8_ENCODING,
)
from config.split_pr_constants import EXIT_CODE_FAILURE
from split_pr_script_types import validate_split_plan
from split_pr_title import normalize_split_title

JsonObject = dict[str, object]


def _is_drive_path(path_text: str) -> bool:
    return len(path_text) >= 2 and path_text[1] == ":"


def normalize_repo_path(raw_path: str) -> str:
    """Normalize a changed-path string for coverage comparison.

    Args:
        raw_path: Path as stored in the plan or intake list.

    Returns:
        Forward-slash path without a leading ``./``.

    Raises:
        ValueError: When the path is empty, absolute, or has ``..`` segments.
    """
    text = raw_path.strip().replace("\\", PATH_SEPARATOR)
    if not text or text.startswith(PATH_SEPARATOR) or _is_drive_path(text):
        raise ValueError(f"unsafe or empty path: {raw_path!r}")
    all_parts = [
        each for each in text.split(PATH_SEPARATOR) if each not in ("", ".")
    ]
    if any(each == ".." for each in all_parts):
        raise ValueError(f"ambiguous parent path segment: {raw_path!r}")
    if not all_parts:
        raise ValueError(f"empty path after normalization: {raw_path!r}")
    return PATH_SEPARATOR.join(all_parts)


def _normalize_plan_paths(all_plan: JsonObject) -> JsonObject:
    all_changed = all_plan.get(PLAN_KEY_ALL_CHANGED_PATHS, [])
    if not isinstance(all_changed, list):
        raise ValueError("all_changed_paths must be a list")
    all_slices = all_plan.get(PLAN_KEY_ALL_SLICES, [])
    if not isinstance(all_slices, list):
        raise ValueError("all_slices must be a list")
    all_normalized_changed = [normalize_repo_path(str(each)) for each in all_changed]
    all_normalized_slices: list[JsonObject] = []
    for each_slice in all_slices:
        if not isinstance(each_slice, dict):
            raise ValueError("slice must be an object")
        all_paths = each_slice.get(SLICE_KEY_ALL_PATHS, [])
        if not isinstance(all_paths, list):
            raise ValueError("slice all_paths must be a list")
        all_normalized_slices.append(
            {
                **each_slice,
                SLICE_KEY_ALL_PATHS: [
                    normalize_repo_path(str(each_path)) for each_path in all_paths
                ],
            }
        )
    return {
        **all_plan,
        PLAN_KEY_ALL_CHANGED_PATHS: all_normalized_changed,
        PLAN_KEY_ALL_SLICES: all_normalized_slices,
    }


def verify_split_plan_coverage(all_plan: JsonObject) -> None:
    """Normalize paths then run the schema assignment validator.

    Args:
        all_plan: Split-plan document.

    Raises:
        ValueError: When coverage or safety checks fail.
    """
    source_commit = all_plan.get(PLAN_KEY_SOURCE_COMMIT)
    if not isinstance(source_commit, str) or not source_commit.strip():
        raise ValueError("source_commit is required")
    normalized = _normalize_plan_paths(all_plan)
    validate_split_plan(normalized)
    all_slices = normalized[PLAN_KEY_ALL_SLICES]
    assert isinstance(all_slices, list)
    for each_slice in all_slices:
        assert isinstance(each_slice, dict)
        title = each_slice.get("title")
        if not isinstance(title, str) or normalize_split_title(title) != title:
            raise ValueError(f"title not normalized: {title!r}")


def main(all_argv: list[str]) -> int:
    """CLI: verify a plan JSON file.

    Args:
        all_argv: Args without program name.

    Returns:
        Exit code 0 on success, 1 on failure.

    Raises:
        Does not raise; converts failures into a JSON error payload.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-json", type=Path, required=True)
    arguments = parser.parse_args(all_argv)
    try:
        payload = json.loads(arguments.plan_json.read_text(encoding=UTF8_ENCODING))
        if not isinstance(payload, dict):
            raise ValueError("plan root must be an object")
        verify_split_plan_coverage(payload)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return EXIT_CODE_FAILURE
    print(json.dumps({"ok": True}))
    return EXIT_CODE_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
