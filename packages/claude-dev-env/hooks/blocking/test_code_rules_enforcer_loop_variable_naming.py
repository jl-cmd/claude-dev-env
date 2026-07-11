from __future__ import annotations

from pathlib import Path
import importlib.util

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location(
    "code_rules_enforcer", ENFORCER_PATH
)
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_FILE_PATH = "packages/app/services/foo.py"
TEST_FILE_PATH = "packages/app/tests/test_foo.py"


def test_should_flag_loop_variable_without_each_prefix() -> None:
    source = "def consume() -> None:\n    for marker in []:\n        return None\n"
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert any("marker" in each_issue for each_issue in issues), (
        f"Expected 'marker' loop variable flagged, got: {issues}"
    )


def test_should_not_flag_loop_variable_with_each_prefix() -> None:
    source = "def consume() -> None:\n    for each_marker in []:\n        return None\n"
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"each_marker must not be flagged, got: {issues}"


def test_should_exempt_index_letters_i_j_k() -> None:
    source = (
        "def consume() -> None:\n"
        "    for i in range(3):\n"
        "        for j in range(3):\n"
        "            for k in range(3):\n"
        "                return None\n"
    )
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"i/j/k must be exempt, got: {issues}"


def test_should_flag_bare_each_without_subject() -> None:
    source = "def consume() -> None:\n    for each in []:\n        return None\n"
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert any("each" in each_issue for each_issue in issues), (
        f"Expected bare 'each' flagged, got: {issues}"
    )


def test_should_flag_tuple_unpacking_targets_lacking_each_prefix() -> None:
    source = (
        "def consume() -> None:\n"
        "    for accessed_field, access_line in []:\n"
        "        return None\n"
    )
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert any("accessed_field" in each_issue for each_issue in issues), (
        f"Expected 'accessed_field' tuple-unpack target flagged, got: {issues}"
    )
    assert any("access_line" in each_issue for each_issue in issues), (
        f"Expected 'access_line' tuple-unpack target flagged, got: {issues}"
    )


def test_should_not_flag_tuple_unpacking_when_all_targets_have_each_prefix() -> None:
    source = (
        "def consume() -> None:\n"
        "    for each_key, each_value in {}.items():\n"
        "        return None\n"
    )
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Tuple-unpack with each_ prefix on all targets must pass, got: {issues}"
    )


def test_should_exempt_underscore_inside_tuple_unpacking() -> None:
    source = (
        "def consume() -> None:\n"
        "    for _, each_position in []:\n"
        "        return None\n"
    )
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"'_' must remain exempt inside tuple unpacking, got: {issues}"
    )


def test_should_flag_partially_compliant_tuple_unpacking() -> None:
    source = (
        "def consume() -> None:\n"
        "    for each_key, raw_value in {}.items():\n"
        "        return None\n"
    )
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert any("raw_value" in each_issue for each_issue in issues), (
        f"Mixed-compliance tuple unpack must flag the offender, got: {issues}"
    )
    assert not any("each_key" in each_issue for each_issue in issues), (
        f"each_key compliant target must not be flagged, got: {issues}"
    )


def test_should_flag_nested_tuple_unpacking_targets() -> None:
    source = (
        "def consume() -> None:\n"
        "    for outer_label, (inner_first, inner_second) in []:\n"
        "        return None\n"
    )
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert any("inner_first" in each_issue for each_issue in issues), (
        f"Nested tuple-unpack targets must be inspected, got: {issues}"
    )
    assert any("inner_second" in each_issue for each_issue in issues), (
        f"Nested tuple-unpack targets must be inspected, got: {issues}"
    )


def test_should_flag_starred_tuple_unpacking_target() -> None:
    source = (
        "def consume() -> None:\n"
        "    for first, *rest in []:\n"
        "        return None\n"
    )
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert any("first" in each_issue for each_issue in issues), (
        f"First tuple-unpack target must be flagged, got: {issues}"
    )
    assert any("rest" in each_issue for each_issue in issues), (
        f"Starred tuple-unpack target must be flagged, got: {issues}"
    )


def test_should_not_flag_list_comprehension_target() -> None:
    source = "def consume() -> None:\n    return [x for x in []]\n"
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Comprehension target exempt, got: {issues}"


def test_should_skip_in_test_files() -> None:
    source = "def test_consume() -> None:\n    for marker in []:\n        return None\n"
    issues = code_rules_enforcer.check_loop_variable_naming(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues}"


def test_should_flag_async_for_loop_variable() -> None:
    source = (
        "async def consume() -> None:\n"
        "    async for marker in stream():\n"
        "        return None\n"
    )
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert any("marker" in each_issue for each_issue in issues), (
        f"Expected async-for variable flagged, got: {issues}"
    )


def test_should_exempt_underscore_throwaway_loop_variable() -> None:
    source = (
        "def consume(count: int) -> None:\n"
        "    for _ in range(count):\n"
        "        return None\n"
    )
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Throwaway '_' loop variable must be exempt (Python idiom for 'value intentionally unused'), got: {issues}"
    )
