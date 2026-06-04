"""Behavior tests for the code_rules_mock_completeness code-rules check module."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_mock_completeness import (  # noqa: E402
    check_incomplete_mocks,
)

code_rules_enforcer = SimpleNamespace(
    check_incomplete_mocks=check_incomplete_mocks,
)


MODULE_LEVEL_MOCK_TEST_FILE_PATH = "packages/app/tests/test_module_level.py"


def _assert_inner_field_did_not_leak(
    captured_stderr: str,
    inner_only_field_name: str,
    binding_form_description: str,
) -> None:
    leaked_advisories = [
        line
        for line in captured_stderr.splitlines()
        if "mock_user" in line and inner_only_field_name in line
    ]
    assert leaked_advisories == [], (
        f"Expected no advisory on the outer mock for {inner_only_field_name!r} — "
        f"that field is accessed only inside a nested scope that re-binds "
        f"mock_user via {binding_form_description}, got: {captured_stderr!r}"
    )


def test_should_treat_try_except_handler_name_as_shadowing(capsys: object) -> None:
    """An ``except ... as mock_user`` handler binds the name locally."""
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    try:\n"
        "        raise ValueError({'id': 2, 'timezone': 'UTC'})\n"
        "    except ValueError as mock_user:\n"
        "        inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "an except-handler binding"
    )


def test_should_treat_walrus_expression_as_shadowing(capsys: object) -> None:
    """A named-expression walrus binding inside a condition must shadow."""
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    if (mock_user := {'id': 2, 'timezone': 'UTC'}):\n"
        "        inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "a walrus named-expression"
    )


def test_should_treat_function_parameter_as_shadowing(capsys: object) -> None:
    """A parameter named like the mock variable must shadow the outer binding."""
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner(mock_user: dict) -> None:\n"
        "    inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "a function parameter of the same name"
    )


def test_should_treat_import_asname_as_shadowing(capsys: object) -> None:
    """An ``import ... as mock_user`` must shadow the outer mock name."""
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    import collections as mock_user\n"
        "    inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "an import-asname binding"
    )
