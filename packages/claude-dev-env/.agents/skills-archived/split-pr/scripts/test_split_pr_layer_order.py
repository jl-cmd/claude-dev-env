"""Layer order is deterministic and config-first."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config.plan_constants import SLICE_KEY_ID, SLICE_KEY_LAYER
from split_pr_layer_order import layer_rank, sort_slices_by_layer_order


def test_layer_rank_orders_config_before_docs() -> None:
    assert layer_rank("config") < layer_rank("docs")
    assert layer_rank("mystery") > layer_rank("other")


def test_sort_places_config_before_docs() -> None:
    all_slices = [
        {SLICE_KEY_ID: "docs", SLICE_KEY_LAYER: "docs"},
        {SLICE_KEY_ID: "config", SLICE_KEY_LAYER: "config"},
    ]
    all_ordered = sort_slices_by_layer_order(all_slices)
    assert [each[SLICE_KEY_ID] for each in all_ordered] == ["config", "docs"]


def test_unknown_layer_sorts_after_known() -> None:
    all_slices = [
        {SLICE_KEY_ID: "z", SLICE_KEY_LAYER: "mystery"},
        {SLICE_KEY_ID: "a", SLICE_KEY_LAYER: "backend"},
    ]
    all_ordered = sort_slices_by_layer_order(all_slices)
    assert [each[SLICE_KEY_ID] for each in all_ordered] == ["a", "z"]
