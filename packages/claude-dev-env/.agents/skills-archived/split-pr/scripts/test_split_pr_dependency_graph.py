"""Dependency graph is deterministic and layer-ordered."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from split_pr_dependency_graph import build_dependency_graph


def test_graph_orders_config_before_docs() -> None:
    all_slices = [
        {"id": "02-docs", "layer": "docs"},
        {"id": "01-config", "layer": "config"},
    ]
    graph = build_dependency_graph(all_slices)
    assert graph["topological_order"] == ["01-config", "02-docs"]
    assert {"from": "01-config", "to": "02-docs"} in graph["edges"]


def test_duplicate_id_fails() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        build_dependency_graph(
            [{"id": "x", "layer": "backend"}, {"id": "x", "layer": "tests"}]
        )


def test_unknown_layer_fails() -> None:
    with pytest.raises(ValueError, match="unknown layer"):
        build_dependency_graph([{"id": "x", "layer": "mystery"}])


def test_same_layer_no_edge() -> None:
    graph = build_dependency_graph(
        [
            {"id": "a", "layer": "backend"},
            {"id": "b", "layer": "backend"},
        ]
    )
    assert graph["edges"] == []
    assert graph["topological_order"] == ["a", "b"]
