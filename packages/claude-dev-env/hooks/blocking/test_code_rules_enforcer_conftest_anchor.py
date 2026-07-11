"""Tests ensuring the conftest pattern matches only the canonical filename."""

import importlib.util
from pathlib import Path


ENFORCER_MODULE_NAME = "code_rules_enforcer_under_test"
ENFORCER_SOURCE_PATH = Path(__file__).parent / "code_rules_enforcer.py"


def load_enforcer_module() -> object:
    module_spec = importlib.util.spec_from_file_location(
        ENFORCER_MODULE_NAME, ENFORCER_SOURCE_PATH
    )
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"cannot load enforcer from {ENFORCER_SOURCE_PATH}")
    enforcer_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(enforcer_module)
    return enforcer_module


enforcer = load_enforcer_module()
is_test_file = enforcer.is_test_file


def test_is_test_file_should_match_canonical_conftest_py() -> None:
    assert is_test_file("C:/proj/tests/conftest.py") is True


def test_is_test_file_should_match_nested_conftest_py() -> None:
    assert is_test_file("C:/proj/subdir/conftest.py") is True


def test_is_test_file_should_not_match_conftest_substring_in_filename() -> None:
    assert is_test_file("C:/proj/my_conftestfile.py") is False


def test_is_test_file_should_not_match_conftest_in_directory_name() -> None:
    assert is_test_file("C:/proj/conftestdata/foo.py") is False


def test_is_test_file_should_not_match_prefixed_conftest_py() -> None:
    assert is_test_file("C:/proj/myconftest.py") is False


def test_is_test_file_should_not_match_underscore_prefixed_conftest_py() -> None:
    assert is_test_file("C:/proj/foo_conftest.py") is False


def test_is_test_file_should_match_conftest_py_with_backslash_separators() -> None:
    assert is_test_file("C:\\proj\\subdir\\conftest.py") is True
