"""Smoke tests for the skill-path fix_hookspath wrap.

Behavioral coverage lives at
``_shared/pr-loop/scripts/tests/test_fix_hookspath.py``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_wrap_module() -> ModuleType:
    module_path = Path(__file__).parent / "bugteam_fix_hookspath.py"
    specification = importlib.util.spec_from_file_location(
        "bugteam_fix_hookspath",
        module_path,
    )
    assert specification is not None
    assert specification.loader is not None
    wrap_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(wrap_module)
    return wrap_module


def test_wrap_main_delegates_to_shared_module() -> None:
    wrap_module = _load_wrap_module()
    assert wrap_module.main.__module__ == "fix_hookspath"
    shared_filename = Path(wrap_module.main.__code__.co_filename).name
    assert shared_filename == "fix_hookspath.py"


def test_wrap_main_help_exits_cleanly() -> None:
    wrap_module = _load_wrap_module()
    try:
        wrap_module.main(["--help"], None)
    except SystemExit as exit_signal:
        assert exit_signal.code in (0, None)
        return
    raise AssertionError("main(['--help'], None) must raise SystemExit")
