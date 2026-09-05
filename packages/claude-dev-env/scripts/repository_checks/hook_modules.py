"""Provide load_hooks_module with the hook package paths on sys.path."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


def load_hooks_module(module_name: str) -> ModuleType:
    """Import a hooks module after placing ``hooks/`` and ``blocking/`` on ``sys.path``.

    ::

        load_hooks_module("blocking.pii_scanner")
        ok:   hooks/ is on sys.path, blocking.pii_scanner imports
        flag: importing a hook main() and printing a deny payload

    Args:
        module_name: Dotted module name under ``hooks/``, such as
            ``blocking.pii_scanner``.

    Returns:
        The imported module.
    """
    package_root = Path(__file__).resolve().parent.parent.parent
    hooks_directory = str(package_root / "hooks")
    blocking_directory = str(package_root / "hooks" / "blocking")
    if blocking_directory not in sys.path:
        sys.path.insert(0, blocking_directory)
    if hooks_directory not in sys.path:
        sys.path.insert(0, hooks_directory)
    return importlib.import_module(module_name)
