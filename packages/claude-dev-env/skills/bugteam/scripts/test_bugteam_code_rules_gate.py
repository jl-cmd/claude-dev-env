"""Smoke tests for the skill-path code_rules_gate wrap.

Behavioral coverage lives at
``_shared/pr-loop/scripts/tests/test_code_rules_gate.py``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_wrap_module() -> ModuleType:
    module_path = Path(__file__).parent / "bugteam_code_rules_gate.py"
    specification = importlib.util.spec_from_file_location(
        "bugteam_code_rules_gate",
        module_path,
    )
    assert specification is not None
    assert specification.loader is not None
    wrap_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(wrap_module)
    return wrap_module


def test_wrap_main_passes_clean_python_file(tmp_path: Path) -> None:
    clean_module_path = tmp_path / "clean_module.py"
    clean_module_path.write_text(
        "def greet() -> str:\n    return 'hi'\n",
        encoding="utf-8",
    )
    wrap_module = _load_wrap_module()
    exit_code = wrap_module.main(
        ["--repo-root", str(tmp_path), str(clean_module_path.name)],
    )
    assert exit_code == 0


def test_wrap_main_help_exits_cleanly() -> None:
    wrap_module = _load_wrap_module()
    try:
        wrap_module.main(["--help"])
    except SystemExit as exit_signal:
        assert exit_signal.code in (0, None)
        return
    raise AssertionError("main(['--help']) must raise SystemExit")
