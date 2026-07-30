"""Canonical split-plan records and validation.

::

    plan = build_split_plan(
        source_commit="abc123",
        all_changed_paths=["a.py", "b.py"],
        all_slices=[{"id": "01-config", "title": "feat: cfg", "layer": "config", "all_paths": ["a.py"]}],
    )
    validate_split_plan(plan)  # raises ValueError when a path is unassigned
"""

from __future__ import annotations

from config.plan_constants import (
    PLAN_KEY_ALL_CHANGED_PATHS,
    PLAN_KEY_ALL_SLICES,
    PLAN_KEY_SCHEMA_VERSION,
    PLAN_KEY_SOURCE_COMMIT,
    PLAN_SCHEMA_VERSION,
    SLICE_KEY_ALL_PATHS,
    SLICE_KEY_ID,
    SLICE_KEY_LAYER,
    SLICE_KEY_TITLE,
)
from split_pr_layer_order import sort_slices_by_layer_order
from split_pr_title import normalize_split_title

JsonObject = dict[str, object]


def build_split_plan(
    source_commit: str,
    all_changed_paths: list[str],
    all_slices: list[JsonObject],
) -> JsonObject:
    """Build a schema-versioned split plan with normalized titles and layer order.

    Args:
        source_commit: Exact commit SHA the file list was taken from.
        all_changed_paths: Full path set for the source commit.
        all_slices: Slice maps with id, title, layer, and path lists.

    Returns:
        Plan document ready for validate_split_plan.
    """
    all_normalized_slices: list[JsonObject] = []
    for each_slice in all_slices:
        title = normalize_split_title(str(each_slice.get(SLICE_KEY_TITLE, "")))
        all_paths = each_slice.get(SLICE_KEY_ALL_PATHS, [])
        if not isinstance(all_paths, list):
            all_paths = []
        all_normalized_slices.append(
            {
                SLICE_KEY_ID: str(each_slice.get(SLICE_KEY_ID, "")),
                SLICE_KEY_TITLE: title,
                SLICE_KEY_LAYER: str(each_slice.get(SLICE_KEY_LAYER, "other")),
                SLICE_KEY_ALL_PATHS: [str(each_path) for each_path in all_paths],
            }
        )
    all_ordered = sort_slices_by_layer_order(all_normalized_slices)
    return {
        PLAN_KEY_SCHEMA_VERSION: PLAN_SCHEMA_VERSION,
        PLAN_KEY_SOURCE_COMMIT: source_commit,
        PLAN_KEY_ALL_CHANGED_PATHS: list(all_changed_paths),
        PLAN_KEY_ALL_SLICES: all_ordered,
    }


def validate_split_plan(all_plan: JsonObject) -> None:
    """Require every changed path is assigned to exactly one slice.

    Args:
        all_plan: Plan document from build_split_plan.

    Raises:
        ValueError: When schema, assignment, or title contracts fail.
    """
    if all_plan.get(PLAN_KEY_SCHEMA_VERSION) != PLAN_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {PLAN_SCHEMA_VERSION}, "
            f"got {all_plan.get(PLAN_KEY_SCHEMA_VERSION)!r}"
        )
    source_commit = all_plan.get(PLAN_KEY_SOURCE_COMMIT)
    if not isinstance(source_commit, str) or not source_commit.strip():
        raise ValueError("source_commit must be a non-empty string")
    all_changed = all_plan.get(PLAN_KEY_ALL_CHANGED_PATHS)
    if not isinstance(all_changed, list):
        raise ValueError("all_changed_paths must be a list")
    all_slices = all_plan.get(PLAN_KEY_ALL_SLICES)
    if not isinstance(all_slices, list) or not all_slices:
        raise ValueError("all_slices must be a non-empty list")
    all_assigned: list[str] = []
    for each_slice in all_slices:
        if not isinstance(each_slice, dict):
            raise ValueError("each slice must be an object")
        title = each_slice.get(SLICE_KEY_TITLE)
        if not isinstance(title, str) or title.count(": ") < 1:
            raise ValueError(f"slice title missing conventional prefix: {title!r}")
        normalized = normalize_split_title(title)
        if normalized != title:
            raise ValueError(
                f"slice title is not normalized: {title!r} != {normalized!r}"
            )
        all_paths = each_slice.get(SLICE_KEY_ALL_PATHS)
        if not isinstance(all_paths, list):
            raise ValueError("slice all_paths must be a list")
        for each_path in all_paths:
            all_assigned.append(str(each_path))
    all_changed_set = {str(each_path) for each_path in all_changed}
    all_assigned_set = set(all_assigned)
    if all_assigned_set != all_changed_set:
        missing = sorted(all_changed_set - all_assigned_set)
        extra = sorted(all_assigned_set - all_changed_set)
        raise ValueError(
            f"path assignment mismatch missing={missing!r} extra={extra!r}"
        )
    if len(all_assigned) != len(all_assigned_set):
        raise ValueError("a path is assigned to more than one slice")
