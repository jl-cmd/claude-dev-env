"""Pack categorized files into review-budgeted split slices.

::

    plan = pack_files_into_slices(
        source_commit="abc",
        all_file_records=[{"path": "a.py", "additions": 50, "deletions": 0}],
    )
    # plan["all_slices"] each stays under the 200 hand-written budget
"""

from __future__ import annotations

from pathlib import Path

from categorize_files import annotate_files
from config.packing_constants import (
    ALL_BACKEND_SUFFIXES,
    ALL_CONFIG_BASENAMES,
    ALL_CONFIG_PATH_MARKERS,
    ALL_DOC_SUFFIXES,
    ALL_FRONTEND_SUFFIXES,
    ALL_TEST_PATH_MARKERS,
    EMPTY_HAND_WRITTEN_SLICE_ID,
    EMPTY_HAND_WRITTEN_TITLE,
    EXCLUDED_CHURN_LAYER_LABEL,
    HARD_CAP_HAND_WRITTEN_LINES,
    LAYER_BACKEND,
    LAYER_CONFIG,
    LAYER_DOCS,
    LAYER_FRONTEND,
    LAYER_OTHER,
    LAYER_TESTS,
    REVIEW_BUDGET_HAND_WRITTEN_LINES,
    SLICE_ID_TEMPLATE,
    SLICE_TITLE_TEMPLATE,
)
from config.split_pr_constants import (
    CHURN_CLASS_HAND_WRITTEN,
    FILE_KEY_CHANGED_LINES,
    FILE_KEY_CHURN_CLASS,
    FILE_KEY_PATH,
)
from split_pr_script_types import build_split_plan, validate_split_plan

JsonObject = dict[str, object]


def infer_path_layer(file_path: str) -> str:
    """Map a path to a packing layer token.

    Args:
        file_path: Repository-relative path.

    Returns:
        One of config/backend/frontend/tests/docs/other.
    """
    normalized = file_path.replace("\\", "/").lower()
    basename = Path(normalized).name
    if basename in ALL_CONFIG_BASENAMES:
        return LAYER_CONFIG
    for each_marker in ALL_CONFIG_PATH_MARKERS:
        if each_marker in f"/{normalized}/" or normalized.startswith(
            each_marker.strip("/")
        ):
            return LAYER_CONFIG
    for each_marker in ALL_TEST_PATH_MARKERS:
        if each_marker in normalized:
            return LAYER_TESTS
    for each_suffix in ALL_DOC_SUFFIXES:
        if normalized.endswith(each_suffix):
            return LAYER_DOCS
    for each_suffix in ALL_FRONTEND_SUFFIXES:
        if normalized.endswith(each_suffix):
            return LAYER_FRONTEND
    for each_suffix in ALL_BACKEND_SUFFIXES:
        if normalized.endswith(each_suffix):
            return LAYER_BACKEND
    return LAYER_OTHER


def _slice_document(
    slice_index: int,
    layer_name: str,
    all_paths: list[str],
    title_layer: str | None = None,
) -> JsonObject:
    title_token = title_layer if title_layer is not None else layer_name
    return {
        "id": SLICE_ID_TEMPLATE.format(index=slice_index, layer=layer_name),
        "title": SLICE_TITLE_TEMPLATE.format(layer=title_token, index=slice_index),
        "layer": layer_name,
        "all_paths": list(all_paths),
    }


def _pack_hand_written_slices(
    all_hand_written: list[JsonObject],
    review_budget: int,
) -> list[JsonObject]:
    all_slices: list[JsonObject] = []
    open_layer: str | None = None
    open_paths: list[str] = []
    open_lines = 0
    slice_index = 1

    def flush_open() -> None:
        nonlocal open_layer, open_paths, open_lines, slice_index
        if open_layer is None or not open_paths:
            open_layer = None
            open_paths = []
            open_lines = 0
            return
        all_slices.append(_slice_document(slice_index, open_layer, open_paths))
        slice_index += 1
        open_layer = None
        open_paths = []
        open_lines = 0

    all_sorted = sorted(
        all_hand_written,
        key=lambda each: (
            infer_path_layer(str(each[FILE_KEY_PATH])),
            str(each[FILE_KEY_PATH]),
        ),
    )
    for each_file in all_sorted:
        path = str(each_file[FILE_KEY_PATH])
        layer = infer_path_layer(path)
        lines = int(each_file.get(FILE_KEY_CHANGED_LINES, 0) or 0)
        if lines > HARD_CAP_HAND_WRITTEN_LINES:
            raise ValueError(
                f"file {path} has {lines} hand-written lines above hard cap "
                f"{HARD_CAP_HAND_WRITTEN_LINES}"
            )
        if open_layer is not None and (
            layer != open_layer or open_lines + lines > review_budget
        ):
            flush_open()
        if open_layer is None:
            open_layer = layer
            open_paths = [path]
            open_lines = lines
        else:
            open_paths.append(path)
            open_lines += lines
    flush_open()
    return all_slices


def pack_files_into_slices(
    source_commit: str,
    all_file_records: list[JsonObject],
    review_budget: int = REVIEW_BUDGET_HAND_WRITTEN_LINES,
) -> JsonObject:
    """Annotate, layer, and pack files into budgeted slices, then build a plan.

    Args:
        source_commit: Exact commit the file list was taken from.
        all_file_records: Path/additions/deletions maps.
        review_budget: Max hand-written lines per slice (default 200).

    Returns:
        Validated split-plan document.

    Raises:
        ValueError: When a single file exceeds the hard 600-line cap alone,
            or plan validation fails.
    """
    if review_budget < 1:
        raise ValueError("review_budget must be positive")
    all_annotated = annotate_files(all_file_records)
    all_changed_paths = [str(each[FILE_KEY_PATH]) for each in all_annotated]
    all_hand_written = [
        each
        for each in all_annotated
        if each.get(FILE_KEY_CHURN_CLASS) == CHURN_CLASS_HAND_WRITTEN
    ]
    all_excluded = [
        each
        for each in all_annotated
        if each.get(FILE_KEY_CHURN_CLASS) != CHURN_CLASS_HAND_WRITTEN
    ]
    all_slices = _pack_hand_written_slices(all_hand_written, review_budget)
    if all_excluded:
        all_slices.append(
            _slice_document(
                len(all_slices) + 1,
                LAYER_OTHER,
                [str(each[FILE_KEY_PATH]) for each in all_excluded],
                title_layer=EXCLUDED_CHURN_LAYER_LABEL,
            )
        )
    if not all_slices and all_changed_paths:
        all_slices.append(
            {
                "id": EMPTY_HAND_WRITTEN_SLICE_ID,
                "title": EMPTY_HAND_WRITTEN_TITLE,
                "layer": LAYER_OTHER,
                "all_paths": list(all_changed_paths),
            }
        )
    plan = build_split_plan(source_commit, all_changed_paths, all_slices)
    validate_split_plan(plan)
    return plan
