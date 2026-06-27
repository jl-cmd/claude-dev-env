"""Tests for check_docstring_documents_unreferenced_parameter.

A parameter named in the ``Args:`` block but referenced nowhere in the body is
dead: the function does not read it, yet the docstring describes behavior keyed
to it. The common shape is a flag a caller wired in before the real logic moved
up a level, leaving the parameter and its Args line claiming a behavior the body
does not implement.
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


def check_documents_unreferenced_parameter(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_documents_unreferenced_parameter(content, file_path)


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/per_theme_loop.py"
TEST_FILE_PATH = "/project/src/test_per_theme_loop.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _function_with_dead_documented_flag() -> str:
    return (
        "def run_per_theme_loop_and_finalize(themes: list, is_no_notify: bool) -> int:\n"
        '    """Run the per-theme loop and finalize the report.\n'
        "\n"
        "    Args:\n"
        "        themes: The themes to process.\n"
        "        is_no_notify: When True, suppresses opening the HTML report.\n"
        "\n"
        "    Returns:\n"
        "        The resolved exit code.\n"
        '    """\n'
        "    exit_code = 0\n"
        "    for each_theme in themes:\n"
        "        exit_code = max(exit_code, each_theme.run())\n"
        "    render_and_write_html_report(themes)\n"
        "    return exit_code\n"
    )


def test_should_flag_documented_parameter_never_referenced() -> None:
    issues = check_documents_unreferenced_parameter(
        _function_with_dead_documented_flag(), PRODUCTION_FILE_PATH
    )
    assert any("is_no_notify" in each for each in issues), (
        f"Expected dead 'is_no_notify' flag, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_not_flag_parameter_referenced_in_body() -> None:
    source = (
        "def run_per_theme_loop_and_finalize(themes: list, is_no_notify: bool) -> int:\n"
        '    """Run the per-theme loop and finalize the report.\n'
        "\n"
        "    Args:\n"
        "        themes: The themes to process.\n"
        "        is_no_notify: When True, suppresses opening the HTML report.\n"
        "\n"
        "    Returns:\n"
        "        The resolved exit code.\n"
        '    """\n'
        "    exit_code = 0\n"
        "    for each_theme in themes:\n"
        "        exit_code = max(exit_code, each_theme.run())\n"
        "    if not is_no_notify:\n"
        "        open_html_report(themes)\n"
        "    return exit_code\n"
    )
    issues = check_documents_unreferenced_parameter(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Referenced parameter must not be flagged, got: {issues!r}"


def test_should_not_flag_when_kwargs_present() -> None:
    source = (
        "def render(themes: list, is_no_notify: bool, **overrides) -> int:\n"
        '    """Render the report.\n'
        "\n"
        "    Args:\n"
        "        themes: The themes to process.\n"
        "        is_no_notify: When True, suppresses opening the report.\n"
        '    """\n'
        "    settings = dict(overrides)\n"
        "    for each_theme in themes:\n"
        "        each_theme.render(settings)\n"
        "    return 0\n"
    )
    issues = check_documents_unreferenced_parameter(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"**kwargs functions must be skipped, got: {issues!r}"


def test_should_skip_private_function() -> None:
    source = (
        "def _drive(themes: list, is_no_notify: bool) -> int:\n"
        '    """Drive internally.\n'
        "\n"
        "    Args:\n"
        "        themes: The themes to process.\n"
        "        is_no_notify: When True, suppresses the report.\n"
        '    """\n'
        "    exit_code = 0\n"
        "    for each_theme in themes:\n"
        "        exit_code = max(exit_code, each_theme.run())\n"
        "    return exit_code\n"
    )
    issues = check_documents_unreferenced_parameter(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Private functions exempt, got: {issues!r}"


def test_should_skip_test_file() -> None:
    issues = check_documents_unreferenced_parameter(
        _function_with_dead_documented_flag(), TEST_FILE_PATH
    )
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_documents_unreferenced_parameter(
        _function_with_dead_documented_flag(), HOOK_INFRASTRUCTURE_PATH
    )
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_documents_unreferenced_parameter("def fetch(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_validate_content_surfaces_unreferenced_parameter() -> None:
    issues = validate_content(
        _function_with_dead_documented_flag(), PRODUCTION_FILE_PATH, old_content=""
    )
    matching_issues = [
        each for each in issues if "is_no_notify" in each and "never references" in each
    ]
    assert matching_issues, (
        f"Expected validate_content to surface the dead-parameter issue, got: {issues!r}"
    )
