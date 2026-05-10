"""Tests for ANY_ALLOWED_PATTERNS exemption from check_type_escape_hatches.

Per Plan 1b: __init__.py, protocols.py, types.py, conftest.py are exempt
from the Any/cast checks because their primary purpose is type re-export
or runtime protocol declaration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()
check_type_escape_hatches = code_rules_enforcer.check_type_escape_hatches

ANY_USING_SOURCE = "from typing import Any\nx: Any = 1\n"


def test_should_exempt_init_py() -> None:
    issues = check_type_escape_hatches(ANY_USING_SOURCE, "/project/src/foo/__init__.py")
    assert issues == [], f"__init__.py must be exempt, got: {issues!r}"


def test_should_exempt_protocols_py() -> None:
    issues = check_type_escape_hatches(ANY_USING_SOURCE, "/project/src/protocols.py")
    assert issues == [], f"protocols.py must be exempt, got: {issues!r}"


def test_should_exempt_types_py() -> None:
    issues = check_type_escape_hatches(ANY_USING_SOURCE, "/project/src/types.py")
    assert issues == [], f"types.py must be exempt, got: {issues!r}"


def test_should_exempt_conftest_py() -> None:
    issues = check_type_escape_hatches(ANY_USING_SOURCE, "/project/src/conftest.py")
    assert issues == [], f"conftest.py must be exempt, got: {issues!r}"


def test_should_still_flag_in_regular_module() -> None:
    issues = check_type_escape_hatches(ANY_USING_SOURCE, "/project/src/models.py")
    assert issues != [], (
        f"Regular .py files must still be flagged for Any usage, got: {issues!r}"
    )


def test_any_type_config_module_exists_and_exposes_constant() -> None:
    config_module_path = Path(__file__).parent.parent / "config" / "any_type_config.py"
    assert config_module_path.is_file(), f"Missing: {config_module_path}"
    spec = importlib.util.spec_from_file_location("any_type_config_under_test", config_module_path)
    assert spec is not None
    assert spec.loader is not None
    loaded_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded_module)
    allowed_patterns = loaded_module.ALL_ANY_ALLOWED_PATTERNS
    assert isinstance(allowed_patterns, tuple)
    assert "__init__.py" in allowed_patterns
    assert "protocols.py" in allowed_patterns
    assert "types.py" in allowed_patterns
    assert "conftest.py" in allowed_patterns
