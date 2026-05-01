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


def test_should_not_flag_tuple_unpacking_targets() -> None:
    source = (
        "def consume() -> None:\n"
        "    for key, value in {}.items():\n"
        "        return None\n"
    )
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Tuple-unpack targets exempt, got: {issues}"


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
