"""Tests for magic-value allowlist alignment with CODE_RULES §HOOK-ENFORCED.

CODE_RULES.md and AGENTS.md both state that only
0, 1, and -1 (plus their float forms 0.0, 1.0) are exempt from the
magic-value check. Prior to this change, the hook silently allowed 2
and 100 as well, making the hook more permissive than the written rule.
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


PRODUCTION_FILE_PATH = "packages/claude-dev-env/hooks/blocking/example_production.py"


def test_check_magic_values_should_flag_literal_two_in_function_body() -> None:
    source = (
        "def compute_something(amount):\n"
        "    threshold = amount * 2\n"
        "    return threshold\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert any(
        issue.endswith("Magic value 2 - extract to named constant") for issue in issues
    ), f"Expected magic-value issue for literal 2, got: {issues}"


def test_check_magic_values_should_flag_literal_one_hundred_in_function_body() -> None:
    source = (
        "def compute_percentage(amount):\n"
        "    scaled = amount * 100\n"
        "    return scaled\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert any(
        issue.endswith("Magic value 100 - extract to named constant") for issue in issues
    ), f"Expected magic-value issue for literal 100, got: {issues}"


def test_check_magic_values_should_still_allow_zero_one_minus_one() -> None:
    source = (
        "def pick_sign(flag: int) -> int:\n"
        "    first = 0\n"
        "    second = 1\n"
        "    third = -1\n"
        "    return first + second + third + flag\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Expected no issues for 0/1/-1, got: {issues}"


def test_check_magic_values_should_still_allow_float_zero_and_float_one() -> None:
    source = (
        "def pick_float(flag: float) -> float:\n"
        "    low = 0.0\n"
        "    high = 1.0\n"
        "    return low + high + flag\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Expected no issues for 0.0/1.0, got: {issues}"
