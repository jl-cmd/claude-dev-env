"""Tests for session/_path_setup path injection."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import hooks_constants


def test_path_setup_puts_hooks_root_on_sys_path() -> None:
    session_dir = Path(__file__).resolve().parent
    hooks_root = str(session_dir.parent)
    path_setup_file = session_dir / "_path_setup.py"
    if hooks_root in sys.path:
        sys.path.remove(hooks_root)

    specification = importlib.util.spec_from_file_location(
        "session_path_setup_under_test", path_setup_file
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    assert hooks_root in sys.path
    assert hooks_constants is not None
