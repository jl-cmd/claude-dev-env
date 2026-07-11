"""Tests that check_magic_values does not flag digits inside string literals.

The regex-based magic-value scan operates on stripped source lines. Before
this fix it matched digits appearing inside string literals (for example the
``8`` inside ``"utf-8"``), producing false positives on any line that passes
an encoding, mode, or similar string kwarg containing a digit. The scanner
must mask string literals before searching for numeric magic values so only
genuine literal numbers in code are reported.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    specification = importlib.util.spec_from_file_location(
        "code_rules_enforcer_for_string_masking_tests",
        module_path,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


PRODUCTION_FILE_PATH = "packages/claude-dev-env/hooks/blocking/example_production.py"


def test_check_magic_values_should_not_flag_digits_inside_double_quoted_string() -> (
    None
):
    source = (
        "def read_configuration(path):\n"
        '    text = path.read_text(encoding="utf-8")\n'
        "    return text\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Expected no issues for utf-8 string, got: {issues}"


def test_check_magic_values_should_not_flag_digits_inside_single_quoted_string() -> (
    None
):
    source = (
        "def read_configuration(path):\n"
        "    text = path.read_text(encoding='utf-8')\n"
        "    return text\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Expected no issues for single-quoted utf-8 string, got: {issues}"
    )


def test_check_magic_values_should_not_flag_digits_inside_multiple_string_kwargs() -> (
    None
):
    source = (
        "def open_log(path):\n"
        '    handle = open(path, mode="rb", encoding="utf-8", errors="replace")\n'
        "    return handle\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Expected no issues for string-only kwargs, got: {issues}"


def test_check_magic_values_should_still_flag_real_magic_value_outside_string() -> None:
    source = (
        "def classify_exit(code: int) -> int:\n"
        "    if code == 5:\n"
        "        return 0\n"
        "    return code\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert any(
        issue.endswith("Magic value 5 - extract to named constant") for issue in issues
    ), f"Expected magic value 5 to be flagged, got: {issues}"


def test_check_magic_values_should_flag_real_number_even_when_line_contains_string() -> (
    None
):
    source = (
        "def classify_exit(code: int) -> int:\n"
        '    marker = "utf-8"\n'
        "    if code == 5:\n"
        "        return 0\n"
        "    return code\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert any(
        issue.endswith("Magic value 5 - extract to named constant") for issue in issues
    ), f"Expected magic value 5 to be flagged alongside string literal, got: {issues}"
    assert not any("Magic value 8" in issue for issue in issues), (
        f"utf-8 should not produce a magic value 8 issue, got: {issues}"
    )
