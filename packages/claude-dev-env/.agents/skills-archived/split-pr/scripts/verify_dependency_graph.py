"""CLI and checks for a split-plan dependency graph document.

::

    python verify_dependency_graph.py --graph-json graph.json
    # exit 0 when shape is valid and order matches a rebuild when all_slices set
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.dependency_constants import (
    EDGE_KEY_FROM,
    EDGE_KEY_TO,
    GRAPH_KEY_EDGES,
    GRAPH_KEY_NODES,
    GRAPH_KEY_ORDER,
)
from config.plan_constants import (
    EXIT_CODE_SUCCESS,
    PLAN_KEY_ALL_SLICES,
    UTF8_ENCODING,
)
from config.split_pr_constants import EXIT_CODE_FAILURE
from split_pr_dependency_graph import build_dependency_graph
from split_pr_script_types import JsonObject


def verify_dependency_graph_document(all_graph: JsonObject) -> None:
    """Validate graph shape; when ``all_slices`` is set, match rebuild order.

    Args:
        all_graph: Graph document with nodes, edges, topological_order, and
            optional ``all_slices``. Always checks: non-empty unique nodes,
            order lists each node once, edges reference known nodes. When
            ``all_slices`` is a non-empty list, rebuilds and requires
            topological_order to match.

    Raises:
        ValueError: When shape checks fail or topological_order mismatches
            a rebuild from ``all_slices``.
    """
    all_nodes = all_graph.get(GRAPH_KEY_NODES)
    all_edges = all_graph.get(GRAPH_KEY_EDGES)
    all_order = all_graph.get(GRAPH_KEY_ORDER)
    if not isinstance(all_nodes, list) or not all_nodes:
        raise ValueError("nodes must be a non-empty list")
    if not isinstance(all_edges, list):
        raise ValueError("edges must be a list")
    if not isinstance(all_order, list):
        raise ValueError("topological_order must be a list")
    all_node_ids = [str(each) for each in all_nodes]
    if len(all_node_ids) != len(set(all_node_ids)):
        raise ValueError("nodes contains duplicates")
    all_order_ids = [str(each) for each in all_order]
    if sorted(all_order_ids) != sorted(all_node_ids):
        raise ValueError("topological_order must list each node exactly once")
    all_node_set = set(all_node_ids)
    for each_edge in all_edges:
        if not isinstance(each_edge, dict):
            raise ValueError("each edge must be an object")
        edge_from = str(each_edge.get(EDGE_KEY_FROM, ""))
        edge_to = str(each_edge.get(EDGE_KEY_TO, ""))
        if edge_from not in all_node_set or edge_to not in all_node_set:
            raise ValueError(f"edge uses unknown node: {each_edge!r}")
    all_slices = all_graph.get(PLAN_KEY_ALL_SLICES)
    if isinstance(all_slices, list) and all_slices:
        rebuilt = build_dependency_graph(all_slices)
        if rebuilt[GRAPH_KEY_ORDER] != all_order_ids:
            raise ValueError(
                f"topological_order mismatch expected {rebuilt[GRAPH_KEY_ORDER]!r} "
                f"got {all_order_ids!r}"
            )


def main(all_argv: list[str]) -> int:
    """CLI entry for graph verification.

    Args:
        all_argv: Args without program name.

    Returns:
        0 on success, 1 on failure.

    Raises:
        Does not raise; writes a JSON error payload on failure.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-json", type=Path, required=True)
    arguments = parser.parse_args(all_argv)
    try:
        payload = json.loads(arguments.graph_json.read_text(encoding=UTF8_ENCODING))
        if not isinstance(payload, dict):
            raise ValueError("graph root must be an object")
        verify_dependency_graph_document(payload)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return EXIT_CODE_FAILURE
    print(json.dumps({"ok": True}))
    return EXIT_CODE_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
