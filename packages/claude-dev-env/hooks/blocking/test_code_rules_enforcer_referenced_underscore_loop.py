from __future__ import annotations

from pathlib import Path
import importlib.util

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location("code_rules_enforcer", ENFORCER_PATH)
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_FILE_PATH = "packages/app/services/foo.py"
CONFTEST_FILE_PATH = "packages/app/tests/conftest.py"


def test_should_flag_referenced_underscore_loop_variable_in_conftest() -> None:
    source = (
        "import sys\n"
        "\n"
        "for _foreign_module_name in ['a', 'b']:\n"
        "    del sys.modules[_foreign_module_name]\n"
    )
    issues = code_rules_enforcer.check_referenced_underscore_loop_variable(
        source, CONFTEST_FILE_PATH
    )
    assert any("_foreign_module_name" in each_issue for each_issue in issues), (
        f"Expected referenced underscore loop variable flagged, got: {issues}"
    )


def test_should_flag_referenced_underscore_loop_variable_in_production() -> None:
    source = (
        "import sys\n"
        "\n"
        "def purge(all_names: list) -> None:\n"
        "    for _name in all_names:\n"
        "        del sys.modules[_name]\n"
    )
    issues = code_rules_enforcer.check_referenced_underscore_loop_variable(
        source, PRODUCTION_FILE_PATH
    )
    assert any("_name" in each_issue for each_issue in issues), (
        f"Expected referenced underscore loop variable flagged, got: {issues}"
    )


def test_should_not_flag_unreferenced_underscore_throwaway() -> None:
    source = "def spin(count: int) -> None:\n    for _unused in range(count):\n        pass\n"
    issues = code_rules_enforcer.check_referenced_underscore_loop_variable(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Genuinely unused underscore throwaway must pass, got: {issues}"


def test_should_not_flag_bare_underscore_target() -> None:
    source = "def spin(count: int) -> None:\n    for _ in range(count):\n        return None\n"
    issues = code_rules_enforcer.check_referenced_underscore_loop_variable(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Bare '_' target must pass, got: {issues}"


def test_should_not_flag_named_loop_variable_without_underscore() -> None:
    source = (
        "import sys\n\nfor each_module_name in ['a', 'b']:\n    del sys.modules[each_module_name]\n"
    )
    issues = code_rules_enforcer.check_referenced_underscore_loop_variable(
        source, CONFTEST_FILE_PATH
    )
    assert issues == [], f"each_-prefixed loop variable without underscore must pass, got: {issues}"


def test_should_not_flag_underscore_loop_variable_shadowed_by_comprehension() -> None:
    source = (
        "def collect(all_names: list, other: list) -> list:\n"
        "    all_other: list = []\n"
        "    for _name in all_names:\n"
        "        all_other = [_name for _name in other]\n"
        "    return all_other\n"
    )
    issues = code_rules_enforcer.check_referenced_underscore_loop_variable(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Comprehension rebinding the loop name shadows the outer read, must pass, got: {issues}"
    )


def test_should_flag_underscore_loop_variable_read_inside_non_rebinding_comprehension() -> None:
    source = (
        "def collect(all_names: list, other: list) -> list:\n"
        "    matches: list = []\n"
        "    for _name in all_names:\n"
        "        matches = [each_row for each_row in other if each_row == _name]\n"
        "    return matches\n"
    )
    issues = code_rules_enforcer.check_referenced_underscore_loop_variable(
        source, PRODUCTION_FILE_PATH
    )
    assert any("_name" in each_issue for each_issue in issues), (
        f"A comprehension reading the outer loop name without rebinding it must flag, got: {issues}"
    )


def test_should_not_flag_underscore_loop_variable_shadowed_by_lambda_parameter() -> None:
    source = (
        "def build(all_names: list) -> list:\n"
        "    all_callables: list = []\n"
        "    for _name in all_names:\n"
        "        all_callables.append(lambda _name: _name)\n"
        "    return all_callables\n"
    )
    issues = code_rules_enforcer.check_referenced_underscore_loop_variable(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"A lambda parameter shadowing the loop name owns its body, must pass, got: {issues}"
    )


def test_should_not_flag_underscore_loop_variable_shadowed_by_nested_def_parameter() -> None:
    source = (
        "def build(all_names: list) -> None:\n"
        "    for _handler in all_names:\n"
        "        def inner(_handler: object) -> object:\n"
        "            return _handler\n"
    )
    issues = code_rules_enforcer.check_referenced_underscore_loop_variable(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"A nested-def parameter shadowing the loop name owns its body, must pass, got: {issues}"
    )


def test_should_not_flag_outer_underscore_loop_variable_shadowed_by_nested_loop() -> None:
    source = (
        "import sys\n"
        "\n"
        "def purge(first: list, second: list) -> None:\n"
        "    for _name in first:\n"
        "        for _name in second:\n"
        "            del sys.modules[_name]\n"
    )
    issues = code_rules_enforcer.check_referenced_underscore_loop_variable(
        source, PRODUCTION_FILE_PATH
    )
    assert not any("Line 4" in each_issue for each_issue in issues), (
        f"Outer loop whose name a nested loop rebinds is never read in the outer scope, "
        f"got: {issues}"
    )


def test_should_flag_underscore_loop_variable_read_before_nested_shadowing_loop() -> None:
    source = (
        "import sys\n"
        "\n"
        "def purge(first: list, second: list) -> None:\n"
        "    for _name in first:\n"
        "        del sys.modules[_name]\n"
        "        for _name in second:\n"
        "            pass\n"
    )
    issues = code_rules_enforcer.check_referenced_underscore_loop_variable(
        source, PRODUCTION_FILE_PATH
    )
    assert any("Line 4" in each_issue for each_issue in issues), (
        f"The outer loop body reads its own name before the nested loop rebinds it, "
        f"must flag, got: {issues}"
    )
