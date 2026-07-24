"""Assign path-layer labels and build proposed PR slices from file paths.

::

    assign_layer("prisma/schema.prisma")  # ok: "database"
    assign_layer("src/api/notify.ts")     # ok: "backend"
    build_slices_from_files([...])        # one slice per non-empty layer in order
"""

from __future__ import annotations

import re

from split_pr_scripts_constants.config.categorize_constants import (
    ALL_LAYER_ORDER,
    ALL_LAYER_PATH_RULES,
    ALL_LAYER_STORY_BY_NAME,
    ALL_LAYER_TITLE_STEM_BY_NAME,
    DEFAULT_LAYER,
)
from split_pr_scripts_constants.config.plan_constants import (
    FILE_KEY_LAYER,
    FILE_KEY_PATH,
    SLICE_KEY_FILES,
    SLICE_KEY_INDEX,
    SLICE_KEY_LAYER,
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


def build_slices_from_files(
    all_files: list[JsonObject],
    feature_slug: str,
    title_prefix: str,
) -> list[JsonObject]:
    """Group annotated files into ordered non-empty layer slices.

    ::

        # files in database + backend layers -> two slices, index 1 then 2

    Args:
        all_files: Annotated file records (``path``, ``layer``).
        feature_slug: Short slug for branch/title context.
        title_prefix: Conventional-commit style prefix (e.g. ``feat``).

    Returns:
        Ordered slice dicts ready for the plan JSON.
    """
    paths_by_layer = _group_paths_by_layer(all_files)
    return _slices_from_layer_map(paths_by_layer, feature_slug, title_prefix)


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
    feature_slug: str,
    title_prefix: str,
) -> list[JsonObject]:
    all_slices: list[JsonObject] = []
    next_index = 1
    for each_layer in ALL_LAYER_ORDER:
        all_paths = sorted(set(paths_by_layer[each_layer]))
        if not all_paths:
            continue
        stem = ALL_LAYER_TITLE_STEM_BY_NAME.get(each_layer, each_layer)
        story = ALL_LAYER_STORY_BY_NAME.get(
            each_layer,
            ALL_LAYER_STORY_BY_NAME[DEFAULT_LAYER],
        )
        title = f"{title_prefix}: {feature_slug} {stem}".strip()
        all_slices.append(
            {
                SLICE_KEY_INDEX: next_index,
                SLICE_KEY_SLUG: each_layer,
                SLICE_KEY_LAYER: each_layer,
                SLICE_KEY_TITLE: title,
                SLICE_KEY_STORY: story,
                SLICE_KEY_FILES: all_paths,
            }
        )
        next_index += 1
    return all_slices
