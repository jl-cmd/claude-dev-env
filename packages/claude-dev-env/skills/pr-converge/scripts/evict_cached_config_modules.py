"""Evict cached ``config`` package bindings before local ``config`` imports.

Mirrors ``_evict_config_module`` in the repository root ``conftest.py``: stale
``config`` or ``config.*`` entries from other packages must not satisfy
``from config.…`` in these scripts after ``sys.path`` inserts the script directory.
"""

from __future__ import annotations

import importlib
import sys


def evict_cached_config_modules() -> None:
    for each_cached_module_name in list(sys.modules):
        is_config_root = each_cached_module_name == "config"
        is_config_submodule = each_cached_module_name.startswith("config.")
        if is_config_root or is_config_submodule:
            sys.modules.pop(each_cached_module_name, None)
    importlib.invalidate_caches()
