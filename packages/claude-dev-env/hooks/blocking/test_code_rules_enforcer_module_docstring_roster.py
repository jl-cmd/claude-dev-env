"""Tests for the module-docstring check roster.

Catches docstring-prose-vs-implementation drift in a check-registry module — a
hook module that exposes several public ``check_*`` functions. The drift the
``code_rules_test_assertions.py`` module hit at PR #713 HEAD: a one-line module
docstring that names four of its five public checks.
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


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content_for_full_gate(content, file_path, old_content)


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


def _registry_module_omitting_check_via_shared_tokens_only() -> str:
    return (
        '"""Bare string-literal magic, inline literal-collection, inline tuple '
        'string-magic, and whitespace-indentation magic checks."""\n'
        "\n"
        "def check_string_literal_magic(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_join_separator_string_magic(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_inline_literal_collections(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_inline_tuple_string_magic(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
        "\n"
        "def check_whitespace_indentation_magic(content: str, file_path: str) -> list[str]:\n"
        "    return []\n"
    )


def test_should_flag_check_named_only_by_tokens_shared_with_siblings() -> None:
    issues = check_module_docstring_names_public_checks(
        _registry_module_omitting_check_via_shared_tokens_only(), HOOK_INFRASTRUCTURE_PATH
    )
    assert any("check_join_separator_string_magic" in each for each in issues), (
        "A check whose only summary-present tokens ('string', 'magic') are shared with "
        f"sibling checks must flag as omitted, got: {issues!r}"
    )
    assert not any("check_string_literal_magic" in each for each in issues), (
        f"A check the summary names ('string-literal magic') must not flag, got: {issues!r}"
    )
    assert not any("check_inline_literal_collections" in each for each in issues), (
        "A check named by a stemmed token ('collection' for 'collections') must not "
        f"flag, got: {issues!r}"
    )
    assert len(issues) == 1


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


def test_imports_logging_module_docstring_names_every_public_check() -> None:
    """The shipped imports-logging module's own roster stays complete after trims."""
    module_path = Path(__file__).resolve().parent / "code_rules_imports_logging.py"
    module_source = module_path.read_text(encoding="utf-8")
    issues = check_module_docstring_names_public_checks(
        module_source, HOOK_INFRASTRUCTURE_PATH
    )
    assert issues == [], f"Roster drift in code_rules_imports_logging.py: {issues!r}"
