"""Tests for evict_cached_config_modules."""

from __future__ import annotations

import sys
import types
from pathlib import Path

_scripts_directory = Path(__file__).resolve().parent
if str(_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_scripts_directory))

from evict_cached_config_modules import evict_cached_config_modules


def test_should_remove_root_config_and_submodules() -> None:
    fake = types.ModuleType("config")
    sys.modules["config"] = fake
    sys.modules["config.stale_submodule"] = types.ModuleType("config.stale_submodule")
    evict_cached_config_modules()
    assert "config" not in sys.modules
    assert "config.stale_submodule" not in sys.modules
