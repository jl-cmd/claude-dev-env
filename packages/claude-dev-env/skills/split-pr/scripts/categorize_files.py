"""Assign path-layer labels and build review-budget PR slices from file paths.

::

    assign_layer("prisma/schema.prisma")  # ok: "database"
    slice_fits_review_budget(file_count=3, changed_lines=120)  # ok: True
    build_slices_from_files([...])  # layers first, then pack oversized layers
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from split_pr_scripts_constants.config.analyze_constants import (
    MAXIMUM_SLICE_CHANGED_LINES,
    MAXIMUM_SLICE_FILE_COUNT,
)
from split_pr_scripts_constants.config.categorize_constants import (
    ALL_LAYER_ORDER,
    ALL_LAYER_PATH_RULES,
    ALL_LAYER_STORY_BY_NAME,
    ALL_LAYER_TITLE_STEM_BY_NAME,
    DEFAULT_LAYER,
    PART_SLUG_SEPARATOR,
    PATH_SEPARATOR,
    WHOLE_PR_SLICE_SLUG,
    WHOLE_PR_SLICE_STORY,
    WHOLE_PR_SLICE_TITLE_STEM,
)
from split_pr_scripts_constants.config.plan_constants import (
    FILE_KEY_ADDITIONS,
    FILE_KEY_DELETIONS,
    FILE_KEY_LAYER,
    FILE_KEY_PATH,
    SLICE_KEY_CHANGED_LINES,
    SLICE_KEY_FILE_COUNT,
    SLICE_KEY_FILES,
    SLICE_KEY_FITS_REVIEW,
    SLICE_KEY_INDEX,
    SLICE_KEY_LAYER,
    SLICE_KEY_OVERSIZED_ATOMIC,
    SLICE_KEY_SLUG,
    SLICE_KEY_STORY,
    SLICE_KEY_TITLE,
)

JsonObject = dict[str, object]


def normalize_path(path: str) -> str:
    """Return a POSIX-style path for rule matching.

    Args:
        path: Raw path from git or GitHub.

    Returns:
        Forward-slash path without a leading ``./``.
    """
    cleaned = path.replace("\\", "/").strip()
    if cleaned.startswith("./"):
        return cleaned[2:]
    return cleaned


def assign_layer(path: str) -> str:
    """Return the dependency layer for one file path.

    ::

        assign_layer("src/components/Bell.tsx")  # ok: frontend
        assign_layer("mystery.bin")              # ok: other

    Args:
        path: Repository-relative path.

    Returns:
        Layer name from the fixed layer catalog.
    """
    normalized = normalize_path(path).lower()
    for each_pattern, each_layer in ALL_LAYER_PATH_RULES:
        if re.search(each_pattern, normalized, flags=re.IGNORECASE) is not None:
            return each_layer
    return DEFAULT_LAYER


def annotate_files(all_files: list[JsonObject]) -> list[JsonObject]:
    """Copy file records and set ``layer`` on each.

    Args:
        all_files: Records that each include at least ``path``.

    Returns:
        New list of records with ``layer`` filled.
    """
    all_annotated: list[JsonObject] = []
    for each_file in all_files:
        annotated: JsonObject = dict(each_file)
        path = str(each_file.get(FILE_KEY_PATH, ""))
        annotated[FILE_KEY_PATH] = normalize_path(path)
        annotated[FILE_KEY_LAYER] = assign_layer(path)
        all_annotated.append(annotated)
    return all_annotated


def slice_fits_review_budget(*, file_count: int, changed_lines: int) -> bool:
    """Return whether a slice is small enough for a focused human review.

    ::

        slice_fits_review_budget(file_count=3, changed_lines=120)  # ok: True
        slice_fits_review_budget(file_count=2, changed_lines=500)  # ok: False

    A slice fits when both budgets hold: at most
    ``MAXIMUM_SLICE_FILE_COUNT`` files and at most
    ``MAXIMUM_SLICE_CHANGED_LINES`` total churn (additions + deletions).

    Args:
        file_count: Number of paths in the slice.
        changed_lines: Sum of additions and deletions across those paths.

    Returns:
        True when both budgets are satisfied.
    """
    return (
        file_count <= MAXIMUM_SLICE_FILE_COUNT
        and changed_lines <= MAXIMUM_SLICE_CHANGED_LINES
    )


def build_slices_from_files(
    all_files: list[JsonObject],
    feature_slug: str,
    title_prefix: str,
) -> list[JsonObject]:
    """Group annotated files into ordered review-budget slices.

    ::

        # one layer with 12 files -> multiple part slices under the review budget

    Layers stay in dependency order. Within a layer that exceeds the review
    budget, files pack by directory prefix, then by individual file size.

    Args:
        all_files: Annotated file records (``path``, ``layer``, optional
            ``additions`` / ``deletions``).
        feature_slug: Short slug for branch/title context.
        title_prefix: Conventional-commit style prefix (e.g. ``feat``).

    Returns:
        Ordered slice dicts ready for the plan JSON.
    """
    churn_by_path = compute_churn_by_path(all_files)
    paths_by_layer = _group_paths_by_layer(all_files)
    return _slices_from_layer_map(
        paths_by_layer,
        churn_by_path,
        feature_slug,
        title_prefix,
    )


def build_whole_pr_slice(
    all_files: list[JsonObject],
    feature_slug: str,
    title_prefix: str,
) -> list[JsonObject]:
    """Return one slice holding every file, for a PR that already fits review.

    ::

        build_whole_pr_slice(all_files, "add-bell", "feat")
        # ok: [{"index": 1, "slug": "whole-pr", "files": [...]}]

    A PR inside the review budget needs no split, so the plan carries a single
    slice. The emitted plan then matches the "split is optional" advice instead
    of contradicting it with a multi-slice stack.

    Args:
        all_files: Annotated file records for the whole pull request.
        feature_slug: Short slug for branch and title context.
        title_prefix: Conventional-commit style prefix (e.g. ``feat``).

    Returns:
        A one-element slice list, or an empty list when no path is present.
    """
    churn_by_path = compute_churn_by_path(all_files)
    all_paths = sorted(churn_by_path)
    if not all_paths:
        return []
    changed_lines = _paths_changed_lines(all_paths, churn_by_path)
    file_count = len(all_paths)
    return [
        {
            SLICE_KEY_INDEX: 1,
            SLICE_KEY_SLUG: WHOLE_PR_SLICE_SLUG,
            SLICE_KEY_LAYER: DEFAULT_LAYER,
            SLICE_KEY_TITLE: (
                f"{title_prefix}: {feature_slug} {WHOLE_PR_SLICE_TITLE_STEM}".strip()
            ),
            SLICE_KEY_STORY: WHOLE_PR_SLICE_STORY,
            SLICE_KEY_FILES: all_paths,
            SLICE_KEY_CHANGED_LINES: changed_lines,
            SLICE_KEY_FILE_COUNT: file_count,
            SLICE_KEY_FITS_REVIEW: slice_fits_review_budget(
                file_count=file_count,
                changed_lines=changed_lines,
            ),
            SLICE_KEY_OVERSIZED_ATOMIC: (
                file_count == 1 and changed_lines > MAXIMUM_SLICE_CHANGED_LINES
            ),
        }
    ]


def compute_churn_by_path(all_records: Sequence[object]) -> dict[str, int]:
    """Return the changed-line budget each file record contributes.

    ::

        compute_churn_by_path([{"path": ".\\\\src\\\\a.py", "additions": 5,
                                "deletions": 1}])
        # ok: {"src/a.py": 6}

    Records that are not objects, and records carrying no path, are skipped.
    Every path normalizes to POSIX form so plan paths and source paths key
    alike. This is the one definition of the budget, shared with the plan
    verifier so the two can never disagree.

    Args:
        all_records: File records carrying ``path`` and optional
            ``additions`` / ``deletions`` counts.

    Returns:
        Mapping of normalized path to additions plus deletions.
    """
    churn_by_path: dict[str, int] = {}
    for each_record in all_records:
        if not isinstance(each_record, dict):
            continue
        raw_path = each_record.get(FILE_KEY_PATH, "")
        if not raw_path:
            continue
        additions = int(each_record.get(FILE_KEY_ADDITIONS, 0) or 0)
        deletions = int(each_record.get(FILE_KEY_DELETIONS, 0) or 0)
        normalized_path = normalize_path(str(raw_path))
        churn_by_path[normalized_path] = max(0, additions) + max(0, deletions)
    return churn_by_path


def _group_paths_by_layer(all_files: list[JsonObject]) -> dict[str, list[str]]:
    paths_by_layer: dict[str, list[str]] = {each: [] for each in ALL_LAYER_ORDER}
    for each_file in all_files:
        layer = str(each_file.get(FILE_KEY_LAYER, DEFAULT_LAYER))
        path = str(each_file.get(FILE_KEY_PATH, ""))
        if not path:
            continue
        if layer not in paths_by_layer:
            paths_by_layer[DEFAULT_LAYER].append(path)
        else:
            paths_by_layer[layer].append(path)
    return paths_by_layer


def _slices_from_layer_map(
    paths_by_layer: dict[str, list[str]],
    churn_by_path: dict[str, int],
    feature_slug: str,
    title_prefix: str,
) -> list[JsonObject]:
    all_slices: list[JsonObject] = []
    next_index = 1
    for each_layer in ALL_LAYER_ORDER:
        all_paths = sorted(set(paths_by_layer[each_layer]))
        if not all_paths:
            continue
        packed_path_groups = _pack_paths_to_review_budget(all_paths, churn_by_path)
        part_count = len(packed_path_groups)
        for each_part_index, each_paths in enumerate(packed_path_groups, start=1):
            slice_record = _build_one_slice(
                layer=each_layer,
                all_paths=each_paths,
                churn_by_path=churn_by_path,
                feature_slug=feature_slug,
                title_prefix=title_prefix,
                slice_index=next_index,
                part_index=each_part_index if part_count > 1 else None,
            )
            all_slices.append(slice_record)
            next_index += 1
    return all_slices


def _build_one_slice(
    *,
    layer: str,
    all_paths: list[str],
    churn_by_path: dict[str, int],
    feature_slug: str,
    title_prefix: str,
    slice_index: int,
    part_index: int | None,
) -> JsonObject:
    stem = ALL_LAYER_TITLE_STEM_BY_NAME.get(layer, layer)
    story = ALL_LAYER_STORY_BY_NAME.get(layer, ALL_LAYER_STORY_BY_NAME[DEFAULT_LAYER])
    part_slug_separator = PART_SLUG_SEPARATOR
    slug = layer if part_index is None else f"{layer}{part_slug_separator}{part_index}"
    title_stem = stem if part_index is None else f"{stem} part {part_index}"
    title = f"{title_prefix}: {feature_slug} {title_stem}".strip()
    changed_lines = _paths_changed_lines(all_paths, churn_by_path)
    file_count = len(all_paths)
    is_fits = slice_fits_review_budget(
        file_count=file_count,
        changed_lines=changed_lines,
    )
    is_oversized_atomic = (
        file_count == 1 and changed_lines > MAXIMUM_SLICE_CHANGED_LINES
    )
    return {
        SLICE_KEY_INDEX: slice_index,
        SLICE_KEY_SLUG: slug,
        SLICE_KEY_LAYER: layer,
        SLICE_KEY_TITLE: title,
        SLICE_KEY_STORY: story,
        SLICE_KEY_FILES: all_paths,
        SLICE_KEY_CHANGED_LINES: changed_lines,
        SLICE_KEY_FILE_COUNT: file_count,
        SLICE_KEY_FITS_REVIEW: is_fits,
        SLICE_KEY_OVERSIZED_ATOMIC: is_oversized_atomic,
    }


def _paths_changed_lines(all_paths: list[str], churn_by_path: dict[str, int]) -> int:
    return sum(churn_by_path.get(each_path, 0) for each_path in all_paths)


@dataclass
class _PathBin:
    """One packed slice under construction, carrying its own running churn.

    Attributes:
        all_paths: Paths placed in this bin so far.
        changed_lines: Sum of the churn of those paths.
    """

    all_paths: list[str] = field(default_factory=list)
    changed_lines: int = 0


def _pack_paths_to_review_budget(
    all_paths: list[str],
    churn_by_path: dict[str, int],
) -> list[list[str]]:
    if not all_paths:
        return []
    if slice_fits_review_budget(
        file_count=len(all_paths),
        changed_lines=_paths_changed_lines(all_paths, churn_by_path),
    ):
        return [list(all_paths)]

    all_bins: list[_PathBin] = []
    for each_group in _groups_by_descending_churn(all_paths, churn_by_path):
        if slice_fits_review_budget(
            file_count=len(each_group.all_paths),
            changed_lines=each_group.changed_lines,
        ):
            _append_group_to_bins(all_bins, each_group)
            continue
        for each_pack in _pack_files_individually(each_group.all_paths, churn_by_path):
            _append_group_to_bins(all_bins, each_pack)
    return [each_bin.all_paths for each_bin in all_bins]


def _groups_by_descending_churn(
    all_paths: list[str],
    churn_by_path: dict[str, int],
) -> list[_PathBin]:
    all_groups = [
        _PathBin(
            all_paths=each_group,
            changed_lines=_paths_changed_lines(each_group, churn_by_path),
        )
        for each_group in _group_paths_by_directory(all_paths)
    ]
    return sorted(
        all_groups,
        key=lambda each_group: (
            -each_group.changed_lines,
            each_group.all_paths[0] if each_group.all_paths else "",
        ),
    )


def _group_paths_by_directory(all_paths: list[str]) -> list[list[str]]:
    paths_by_directory: dict[str, list[str]] = {}
    for each_path in sorted(all_paths):
        directory_key = _directory_key(each_path)
        paths_by_directory.setdefault(directory_key, []).append(each_path)
    return list(paths_by_directory.values())


def _directory_key(path: str) -> str:
    if PATH_SEPARATOR not in path:
        return path
    return path.rsplit(PATH_SEPARATOR, 1)[0]


def _pack_files_individually(
    all_paths: list[str],
    churn_by_path: dict[str, int],
) -> list[_PathBin]:
    sorted_paths = sorted(
        all_paths,
        key=lambda each_path: (-churn_by_path.get(each_path, 0), each_path),
    )
    all_bins: list[_PathBin] = []
    for each_path in sorted_paths:
        single_path_bin = _PathBin(
            all_paths=[each_path],
            changed_lines=churn_by_path.get(each_path, 0),
        )
        _append_group_to_bins(all_bins, single_path_bin)
    return all_bins


def _append_group_to_bins(all_bins: list[_PathBin], group: _PathBin) -> None:
    for each_bin in all_bins:
        if slice_fits_review_budget(
            file_count=len(each_bin.all_paths) + len(group.all_paths),
            changed_lines=each_bin.changed_lines + group.changed_lines,
        ):
            each_bin.all_paths.extend(group.all_paths)
            each_bin.changed_lines += group.changed_lines
            return
    all_bins.append(
        _PathBin(all_paths=list(group.all_paths), changed_lines=group.changed_lines)
    )
