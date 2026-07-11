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


INCOMPLETE_MOCK_PRODUCTION_FILE_PATH = "packages/app/services/orders.py"

INCOMPLETE_MOCK_TEST_FILE_PATH = "packages/app/tests/test_orders.py"

MODULE_LEVEL_MOCK_TEST_FILE_PATH = "packages/app/tests/test_module_level.py"

SCOPE_KEYED_MOCK_TEST_FILE_PATH = "packages/app/tests/test_scope_mocks.py"


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


def test_should_advise_when_mock_missing_accessed_field(capsys: object) -> None:
    source = (
        "mock_order = {'id': 1}\n"
        "\n"
        "def test_order_total() -> None:\n"
        "    total = mock_order['total']\n"
        "    assert total > 0\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" in captured.err and "total" in captured.err, (
        f"Expected advisory about missing 'total' field, got: {captured.err!r}"
    )


def test_should_not_advise_when_mock_has_all_accessed_fields(capsys: object) -> None:
    source = (
        "mock_order = {'id': 1, 'total': 50}\n"
        "\n"
        "def test_order_total() -> None:\n"
        "    total = mock_order['total']\n"
        "    assert total > 0\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" not in captured.err, (
        f"Expected no advisory when all fields present, got: {captured.err!r}"
    )


def test_should_not_advise_for_incomplete_mocks_in_production_files(capsys: object) -> None:
    source = (
        "mock_order = {'id': 1}\n"
        "\n"
        "def run_order() -> None:\n"
        "    total = mock_order['total']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_PRODUCTION_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" not in captured.err, (
        f"Expected no advisory in production file, got: {captured.err!r}"
    )


def test_should_advise_for_attribute_access_on_mock_object(capsys: object) -> None:
    source = (
        "class MockUser:\n"
        "    pass\n"
        "\n"
        "mock_user = MockUser()\n"
        "mock_user.name = 'Alice'\n"
        "\n"
        "def test_user_email() -> None:\n"
        "    email = mock_user.email\n"
        "    assert email\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_user" in captured.err and "email" in captured.err, (
        f"Expected advisory about missing 'email' attribute, got: {captured.err!r}"
    )


def test_should_advise_when_mock_defined_inside_test_function_is_incomplete(
    capsys: object,
) -> None:
    source = (
        "def test_thing() -> None:\n"
        "    mock_user = {'name': 'x'}\n"
        "    assert mock_user['email'] == 'y'\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_user" in captured.err and "email" in captured.err, (
        f"Expected advisory for mock defined inside test function, got: {captured.err!r}"
    )


def test_should_check_each_scope_mock_against_its_own_field_set(capsys: object) -> None:
    """Same mock_user name in two test functions with different field sets.

    First function defines mock_user with only 'id'; accesses 'email' — should warn.
    Second function defines mock_user with 'id' and 'email'; accesses 'email' — no warn.
    The second definition must NOT overwrite the first scope's tracking.
    """
    source = (
        "def test_first_scope() -> None:\n"
        "    mock_user = {'id': 1}\n"
        "    email = mock_user['email']\n"
        "\n"
        "def test_second_scope() -> None:\n"
        "    mock_user = {'id': 2, 'email': 'b@b.com'}\n"
        "    email = mock_user['email']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, SCOPE_KEYED_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    advisory_lines = [
        line for line in captured.err.splitlines() if "mock_user" in line and "email" in line
    ]
    assert len(advisory_lines) == 1, (
        f"Expected exactly 1 advisory (first scope missing email), got: {captured.err!r}"
    )


def test_should_emit_exactly_one_advisory_for_repeated_accesses_to_same_missing_field(
    capsys: object,
) -> None:
    """mock_user accessed 5 times for 'email' but email is missing — emit exactly one advisory."""
    source = (
        "def test_repeated_access() -> None:\n"
        "    mock_user = {'id': 1}\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, SCOPE_KEYED_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    advisory_lines = [
        line for line in captured.err.splitlines() if "mock_user" in line and "email" in line
    ]
    assert len(advisory_lines) == 1, (
        f"Expected exactly 1 advisory for 5 repeated accesses to missing 'email', got: {captured.err!r}"
    )


def test_should_emit_exactly_one_advisory_for_module_level_mock_with_missing_field(
    capsys: object,
) -> None:
    """Module-level mock_user with one missing field access should produce ONE advisory.

    Finding 4: ast.walk() already yields the root Module node, so
    [module_tree, *ast.walk(module_tree)] iterates the module twice and
    previously produced two identical advisories for module-level mocks.
    """
    source = (
        "mock_user = {'name': 'Alice'}\n"
        "\n"
        "def test_email_present() -> None:\n"
        "    email = mock_user['email']\n"
        "    assert email\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    advisory_lines = [
        line for line in captured.err.splitlines() if "mock_user" in line and "email" in line
    ]
    assert len(advisory_lines) == 1, (
        f"Expected exactly 1 advisory for module-level mock missing 'email', got: {captured.err!r}"
    )


def test_should_not_leak_shadowed_nested_assignment_into_outer_mock_known_fields(
    capsys: object,
) -> None:
    """Assignment collector must skip nested scopes that shadow the mock name.

    The access collector uses _walk_scope_skipping_shadowed; the assignment
    collector must do the same, otherwise attribute assignments inside a
    nested function that redefines mock_user leak into the outer mock's
    known-fields set and suppress advisories for genuinely missing fields.
    """
    source = (
        "mock_user = {'id': 1}\n"
        "outer_value = mock_user['email']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    mock_user = {'id': 2}\n"
        "    mock_user.email = 'shadowed@example.com'\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    advisory_lines = [
        line for line in captured.err.splitlines() if "mock_user" in line and "email" in line
    ]
    assert len(advisory_lines) == 1, (
        "Expected outer mock's missing 'email' advisory to fire even when a shadowing "
        f"nested function assigns mock_user.email, got: {captured.err!r}"
    )


def test_should_treat_annotated_assignment_as_shadowing_in_nested_scope(
    capsys: object,
) -> None:
    """AnnAssign must shadow just like Assign.

    When a nested scope re-binds the mock variable via an annotated
    assignment (``mock_user: dict = {...}``), accesses inside that nested
    scope belong to the inner mock, not the outer one. If the shadow
    detector ignores AnnAssign, inner accesses leak out and cause
    spurious advisories against the outer mock for fields it never sees.
    """
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    mock_user: dict = {'id': 2, 'timezone': 'UTC'}\n"
        "    inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    leaked_advisories = [
        line
        for line in captured.err.splitlines()
        if "mock_user" in line and "timezone" in line
    ]
    assert leaked_advisories == [], (
        "Expected no advisory on the outer mock for 'timezone' — that field is "
        "accessed only inside a nested scope that re-binds mock_user via an "
        f"annotated assignment, got: {captured.err!r}"
    )


def test_should_treat_assignment_inside_if_block_as_shadowing(capsys: object) -> None:
    """Binding inside an ``if`` block must shadow the outer mock name.

    Python binds a name locally when it is assigned *anywhere* in the
    function body, including inside a branch. A shadow detector that only
    inspects the top-level statements misses this form.
    """
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    if True:\n"
        "        mock_user = {'id': 2, 'timezone': 'UTC'}\n"
        "    inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "an assignment nested inside an if-block"
    )


def test_should_treat_for_loop_target_as_shadowing(capsys: object) -> None:
    """A ``for`` loop target binds the name locally and must shadow."""
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    for mock_user in [{'id': 2, 'timezone': 'UTC'}]:\n"
        "        inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "a for-loop target"
    )
