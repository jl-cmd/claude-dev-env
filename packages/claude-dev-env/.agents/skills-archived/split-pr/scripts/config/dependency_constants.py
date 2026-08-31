"""Constants for deterministic split-slice dependency graphs."""

from __future__ import annotations

from config.plan_constants import ALL_LAYER_ORDER

GRAPH_KEY_NODES: str = "nodes"
GRAPH_KEY_EDGES: str = "edges"
GRAPH_KEY_ORDER: str = "topological_order"
EDGE_KEY_FROM: str = "from"
EDGE_KEY_TO: str = "to"
ALL_LAYER_RANK_BY_NAME: dict[str, int] = {
    each_layer: each_index for each_index, each_layer in enumerate(ALL_LAYER_ORDER)
}
