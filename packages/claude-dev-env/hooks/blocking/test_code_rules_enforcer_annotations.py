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


def test_should_flag_parameter_without_annotation() -> None:
    source = "def consume(value) -> None:\n    return None\n"
    issues = code_rules_enforcer.check_parameter_annotations(
        source, PRODUCTION_FILE_PATH
    )
    assert any("value" in each_issue for each_issue in issues), (
        f"Expected unannotated parameter flagged, got: {issues}"
    )


def test_should_not_flag_annotated_parameters() -> None:
    source = (
        "def consume(value: int, label: str = 'default') -> None:\n    return None\n"
    )
    issues = code_rules_enforcer.check_parameter_annotations(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Expected no issues for annotated params, got: {issues}"


def test_should_exempt_self_and_cls_parameters() -> None:
    source = (
        "class Foo:\n"
        "    def method(self, value: int) -> None:\n"
        "        return None\n"
        "    @classmethod\n"
        "    def factory(cls, value: int) -> 'Foo':\n"
        "        return cls()\n"
    )
    issues = code_rules_enforcer.check_parameter_annotations(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"self/cls must be exempt from annotation requirement, got: {issues}"
    )


def test_should_flag_class_method_parameter_without_annotation() -> None:
    source = "class Foo:\n    def method(self, value) -> None:\n        return None\n"
    issues = code_rules_enforcer.check_parameter_annotations(
        source, PRODUCTION_FILE_PATH
    )
    assert any("value" in each_issue for each_issue in issues), (
        f"Expected method param flagged, got: {issues}"
    )


def test_should_skip_parameter_check_in_test_files() -> None:
    source = "def consume(value) -> None:\n    return None\n"
    issues = code_rules_enforcer.check_parameter_annotations(source, TEST_FILE_PATH)
    assert issues == [], f"Test files must be exempt, got: {issues}"


def test_should_flag_function_without_return_annotation() -> None:
    source = "def fetch(url: str):\n    return url\n"
    issues = code_rules_enforcer.check_return_annotations(source, PRODUCTION_FILE_PATH)
    assert any("fetch" in each_issue for each_issue in issues), (
        f"Expected function without return type flagged, got: {issues}"
    )


def test_should_not_flag_function_with_return_annotation() -> None:
    source = "def fetch(url: str) -> str:\n    return url\n"
    issues = code_rules_enforcer.check_return_annotations(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Function with return type must not be flagged, got: {issues}"


def test_should_flag_async_function_without_return_annotation() -> None:
    source = "async def fetch(url: str):\n    return url\n"
    issues = code_rules_enforcer.check_return_annotations(source, PRODUCTION_FILE_PATH)
    assert any("fetch" in each_issue for each_issue in issues), (
        f"Expected async function without return type flagged, got: {issues}"
    )


def test_should_skip_return_check_in_test_files() -> None:
    source = "def fetch(url: str):\n    return url\n"
    issues = code_rules_enforcer.check_return_annotations(source, TEST_FILE_PATH)
    assert issues == [], f"Test files must be exempt, got: {issues}"


