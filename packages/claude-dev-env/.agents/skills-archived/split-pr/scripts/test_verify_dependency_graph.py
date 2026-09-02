"""Dependency graph verifier CLI and rebuild checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from split_pr_dependency_graph import build_dependency_graph
from verify_dependency_graph import main, verify_dependency_graph_document


def test_verify_accepts_rebuilt_graph() -> None:
    all_slices = [
        {"id": "01-config", "layer": "config"},
        {"id": "02-docs", "layer": "docs"},
    ]
    graph = build_dependency_graph(all_slices)
    graph["all_slices"] = all_slices
    verify_dependency_graph_document(graph)


def test_verify_rejects_order_mismatch() -> None:
    all_slices = [
        {"id": "01-config", "layer": "config"},
        {"id": "02-docs", "layer": "docs"},
    ]
    graph = build_dependency_graph(all_slices)
    graph["all_slices"] = all_slices
    graph["topological_order"] = ["02-docs", "01-config"]
    with pytest.raises(ValueError, match="mismatch"):
        verify_dependency_graph_document(graph)


def test_cli_ok(tmp_path: Path) -> None:
    all_slices = [{"id": "a", "layer": "backend"}]
    graph = build_dependency_graph(all_slices)
    path = tmp_path / "g.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    assert main(["--graph-json", str(path)]) == 0
