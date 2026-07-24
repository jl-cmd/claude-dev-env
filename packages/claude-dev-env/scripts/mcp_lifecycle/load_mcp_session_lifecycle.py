"""Shared loader for hooks lifecycle mcp_session_lifecycle module from scripts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_mcp_session_lifecycle_module() -> ModuleType:
    """Import mcp_session_lifecycle via path bootstrap; return the module.

    Returns:
        Loaded mcp_session_lifecycle module.
    """
    script_package_dir = Path(__file__).resolve().parent
    scripts_dir = str(script_package_dir.parent)
    hooks_dir = str(Path(scripts_dir).parent / "hooks")
    lifecycle_dir_path = Path(hooks_dir) / "lifecycle"
    lifecycle_dir = str(lifecycle_dir_path)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    if lifecycle_dir not in sys.path:
        sys.path.insert(0, lifecycle_dir)
    lifecycle_spec = importlib.util.spec_from_file_location(
        "mcp_session_lifecycle",
        lifecycle_dir_path / "mcp_session_lifecycle.py",
    )
    assert lifecycle_spec is not None
    assert lifecycle_spec.loader is not None
    loaded_lifecycle = importlib.util.module_from_spec(lifecycle_spec)
    lifecycle_spec.loader.exec_module(loaded_lifecycle)
    return loaded_lifecycle
