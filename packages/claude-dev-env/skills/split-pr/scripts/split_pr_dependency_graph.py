"""Build a deterministic dependency graph over split-plan slices.

::

    graph = build_dependency_graph(all_slices)
    # edges: lower-rank layers must land before higher-rank layers

Invalid cycles and unknown layers fail with exact diagnostics.
"""

from __future__ import annotations

from config.dependency_constants import (
    EDGE_KEY_FROM,
    EDGE_KEY_TO,
    GRAPH_KEY_EDGES,
    GRAPH_KEY_NODES,
    GRAPH_KEY_ORDER,
    ALL_LAYER_RANK_BY_NAME,
)
from config.plan_constants import SLICE_KEY_ID, SLICE_KEY_LAYER

JsonObject = dict[str, object]


def build_dependency_graph(all_slices: list[JsonObject]) -> JsonObject:
    """Return nodes, layer-order edges, and a stable topological order.

    Args:
        all_slices: Slice maps with ``id`` and ``layer``.

    Returns:
        Graph document with nodes, edges, and topological_order.

    Raises:
        ValueError: When a layer is unknown or the graph would cycle
            (should not happen under pure layer edges).
    """
    if not all_slices:
        raise ValueError("all_slices must be non-empty")
    all_nodes: list[str] = []
    all_layer_by_id: dict[str, str] = {}
    for each_slice in all_slices:
        slice_id = str(each_slice.get(SLICE_KEY_ID, "") or "")
        if not slice_id:
            raise ValueError("every slice needs a non-empty id")
        if slice_id in all_layer_by_id:
            raise ValueError(f"duplicate slice id: {slice_id}")
        layer = str(each_slice.get(SLICE_KEY_LAYER, "other") or "other")
        if layer not in ALL_LAYER_RANK_BY_NAME:
            raise ValueError(f"unknown layer {layer!r} on slice {slice_id}")
        all_nodes.append(slice_id)
        all_layer_by_id[slice_id] = layer
    all_edges: list[JsonObject] = []
    for each_from in all_nodes:
        for each_to in all_nodes:
            if each_from == each_to:
                continue
            from_rank = ALL_LAYER_RANK_BY_NAME[all_layer_by_id[each_from]]
            to_rank = ALL_LAYER_RANK_BY_NAME[all_layer_by_id[each_to]]
            if from_rank < to_rank:
                all_edges.append({EDGE_KEY_FROM: each_from, EDGE_KEY_TO: each_to})
    all_order = sorted(
        all_nodes,
        key=lambda each_id: (ALL_LAYER_RANK_BY_NAME[all_layer_by_id[each_id]], each_id),
    )
    return {
        GRAPH_KEY_NODES: all_nodes,
        GRAPH_KEY_EDGES: all_edges,
        GRAPH_KEY_ORDER: all_order,
    }
