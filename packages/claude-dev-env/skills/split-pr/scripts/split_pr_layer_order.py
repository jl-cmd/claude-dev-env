"""Deterministic layer order for split-plan slices.

::

    sort_slices_by_layer_order([{"layer": "docs"}, {"layer": "config"}])
    # config first, then docs
"""

from __future__ import annotations

from config.plan_constants import (
    ALL_LAYER_RANK_BY_NAME,
    DEFAULT_SLICE_LAYER,
    SLICE_KEY_LAYER,
    UNKNOWN_LAYER_RANK,
)

JsonObject = dict[str, object]


def layer_rank(layer_name: str) -> int:
    """Return the stable rank for a layer name (unknown layers sort last).

    Args:
        layer_name: Layer token such as ``config`` or ``tests``.

    Returns:
        Integer rank; lower values sort earlier.
    """
    return ALL_LAYER_RANK_BY_NAME.get(layer_name, UNKNOWN_LAYER_RANK)


def sort_slices_by_layer_order(all_slices: list[JsonObject]) -> list[JsonObject]:
    """Return a new list of slices sorted by layer rank then original index.

    Args:
        all_slices: Slice maps that may carry a ``layer`` key.

    Returns:
        Fresh list sorted stably by layer rank.
    """
    all_indexed_slices = list(enumerate(all_slices))

    def _rank_for_sort(
        all_indexed_slice: tuple[int, JsonObject],
    ) -> tuple[int, int]:
        each_index, each_slice = all_indexed_slice
        layer_field = each_slice.get(SLICE_KEY_LAYER, DEFAULT_SLICE_LAYER)
        if layer_field is None:
            layer_name = DEFAULT_SLICE_LAYER
        else:
            layer_name = str(layer_field)
        return (layer_rank(layer_name), each_index)

    return [
        each_slice
        for _each_index, each_slice in sorted(all_indexed_slices, key=_rank_for_sort)
    ]
