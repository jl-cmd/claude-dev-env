"""Tests for the module-docstring check roster and docstring tuple-enumeration checks.

Both checks catch docstring-prose-vs-implementation drift in a check-registry
module — a hook module that exposes several public ``check_*`` functions and a
module-level tuple of literal attribute names. The drift the
``code_rules_test_assertions.py`` module hit at PR #713 HEAD: a one-line module
docstring that names four of its five public checks, and a function docstring
that enumerates three plumbing attributes while the tuple it reads holds four.
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


def check_module_docstring_names_public_checks(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_module_docstring_names_public_checks(content, file_path)


def check_docstring_tuple_enumeration_match(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_tuple_enumeration_match(content, file_path)


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/code_rules_test_assertions.py"
PRODUCTION_FILE_PATH = "/project/src/registry.py"
TEST_FILE_PATH = "/project/src/test_registry.py"


def _registry_module_omitting_a_check() -> str:
    return (
        '"""Skip-decorator, existence-only, and constant-equality test-quality checks."""\n'
        "\n"
        "def check_skip_decorators(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_existence_check(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_constant_equality(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_behavior_named_mock(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
    )


def test_should_flag_module_docstring_omitting_a_public_check() -> None:
    issues = check_module_docstring_names_public_checks(
        _registry_module_omitting_a_check(), HOOK_INFRASTRUCTURE_PATH
    )
    assert any("check_behavior_named_mock" in each for each in issues), (
        f"Expected the omitted check to flag, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_not_flag_module_docstring_naming_every_public_check() -> None:
    source = (
        '"""Skip-decorator, existence-check, constant-equality, and behavior-named-mock checks."""\n'
        "\n"
        "def check_skip_decorators(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_existence_check(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_constant_equality(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_behavior_named_mock(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
    )
    issues = check_module_docstring_names_public_checks(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Docstring naming every check must not flag, got: {issues!r}"


def test_should_not_flag_module_with_a_single_public_check() -> None:
    source = (
        '"""Skip-decorator test-quality check."""\n'
        "\n"
        "def check_skip_decorators(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
    )
    issues = check_module_docstring_names_public_checks(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"A one-check module must not flag, got: {issues!r}"


def test_should_not_flag_multi_paragraph_module_docstring() -> None:
    source = (
        '"""Skip-decorator and existence-check test-quality checks.\n'
        "\n"
        "    The roster grows over time; the audit lane reads the full prose body.\n"
        '    """\n'
        "\n"
        "def check_skip_decorators(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_behavior_named_mock(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
    )
    issues = check_module_docstring_names_public_checks(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Multi-paragraph docstrings go to the audit lane, got: {issues!r}"


def test_should_skip_module_without_docstring() -> None:
    source = (
        "def check_skip_decorators(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_behavior_named_mock(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
    )
    issues = check_module_docstring_names_public_checks(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"No-docstring modules are out of scope, got: {issues!r}"


def test_should_skip_private_check_helpers() -> None:
    source = (
        '"""Skip-decorator and existence-check test-quality checks."""\n'
        "\n"
        "def check_skip_decorators(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_existence_check(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def _check_internal_helper(content: str) -> bool:\n"
        "    return False\n"
    )
    issues = check_module_docstring_names_public_checks(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Private check helpers are not roster surface, got: {issues!r}"


def test_should_skip_test_file_for_module_roster() -> None:
    issues = check_module_docstring_names_public_checks(
        _registry_module_omitting_a_check(), TEST_FILE_PATH
    )
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_handle_module_roster_syntax_error_gracefully() -> None:
    issues = check_module_docstring_names_public_checks("def broken(\n", HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def _module_with_drifted_tuple_enumeration() -> str:
    return (
        '"""Call-args plumbing detection."""\n'
        "\n"
        '_CALL_ARGS_PLUMBING_ATTRIBUTES = ("call_args", "call_args_list", "called", "call_count")\n'
        "\n"
        "def check_plumbing(content: str, file_path: str) -> list[str]:\n"
        '    """Advise when a test asserts only on call-args plumbing.\n'
        "\n"
        "    A body asserting on call-args plumbing (``call_args``, ``call_args_list``,\n"
        "    ``.kwargs``) reaches into mock internals rather than observed behavior.\n"
        '    """\n'
        "    for each_name in _CALL_ARGS_PLUMBING_ATTRIBUTES:\n"
        "        if each_name in content:\n"
        "            return [each_name]\n"
        "    return []\n"
    )


def test_should_flag_docstring_tuple_enumeration_drift() -> None:
    issues = check_docstring_tuple_enumeration_match(
        _module_with_drifted_tuple_enumeration(), HOOK_INFRASTRUCTURE_PATH
    )
    assert any("check_plumbing" in each for each in issues), (
        f"Expected the drifted enumeration to flag, got: {issues!r}"
    )
    assert any("kwargs" in each for each in issues), (
        f"Expected the docstring-only token named in the message, got: {issues!r}"
    )
    assert any("called" in each for each in issues), (
        f"Expected a tuple-only member named in the message, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_not_flag_docstring_tuple_enumeration_match() -> None:
    source = (
        '"""Call-args plumbing detection."""\n'
        "\n"
        '_CALL_ARGS_PLUMBING_ATTRIBUTES = ("call_args", "call_args_list", "called", "call_count")\n'
        "\n"
        "def check_plumbing(content: str, file_path: str) -> list[str]:\n"
        '    """Advise when a test asserts only on call-args plumbing.\n'
        "\n"
        "    A body asserting on call-args plumbing (``call_args``, ``call_args_list``,\n"
        "    ``called``, ``call_count``) reaches into mock internals.\n"
        '    """\n'
        "    for each_name in _CALL_ARGS_PLUMBING_ATTRIBUTES:\n"
        "        if each_name in content:\n"
        "            return [each_name]\n"
        "    return []\n"
    )
    issues = check_docstring_tuple_enumeration_match(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Matching enumeration must not flag, got: {issues!r}"


def test_should_not_flag_docstring_without_tuple_overlap() -> None:
    source = (
        '"""Call-args plumbing detection."""\n'
        "\n"
        '_CALL_ARGS_PLUMBING_ATTRIBUTES = ("call_args", "call_args_list", "called", "call_count")\n'
        "\n"
        "def check_plumbing(content: str, file_path: str) -> list[str]:\n"
        '    """Advise when a test asserts only on mock internals.\n'
        "\n"
        "    A body reading ``foo``, ``bar``, ``baz`` is unrelated to the tuple.\n"
        '    """\n'
        "    for each_name in _CALL_ARGS_PLUMBING_ATTRIBUTES:\n"
        "        if each_name in content:\n"
        "            return [each_name]\n"
        "    return []\n"
    )
    issues = check_docstring_tuple_enumeration_match(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"A docstring not naming the tuple must not flag, got: {issues!r}"


def test_should_not_flag_when_function_does_not_reference_the_tuple() -> None:
    source = (
        '"""Call-args plumbing detection."""\n'
        "\n"
        '_CALL_ARGS_PLUMBING_ATTRIBUTES = ("call_args", "call_args_list", "called", "call_count")\n'
        "\n"
        "def check_unrelated(content: str, file_path: str) -> list[str]:\n"
        '    """Advise on ``call_args`` and ``call_args_list`` usage in tests."""\n'
        "    return [content[:0]]\n"
    )
    issues = check_docstring_tuple_enumeration_match(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"A function not reading the tuple must not flag, got: {issues!r}"


def test_should_handle_tuple_enumeration_syntax_error_gracefully() -> None:
    issues = check_docstring_tuple_enumeration_match("def broken(\n", HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_validate_content_surfaces_module_roster_drift() -> None:
    issues = validate_content(
        _registry_module_omitting_a_check(), HOOK_INFRASTRUCTURE_PATH, old_content=""
    )
    matching_issues = [
        each for each in issues if "check_behavior_named_mock" in each and "docstring" in each
    ]
    assert matching_issues, (
        f"Expected validate_content to surface the module-roster drift, got: {issues!r}"
    )


def test_validate_content_surfaces_tuple_enumeration_drift() -> None:
    issues = validate_content(
        _module_with_drifted_tuple_enumeration(), HOOK_INFRASTRUCTURE_PATH, old_content=""
    )
    matching_issues = [each for each in issues if "check_plumbing" in each and "enumerat" in each]
    assert matching_issues, (
        f"Expected validate_content to surface the tuple-enumeration drift, got: {issues!r}"
    )
