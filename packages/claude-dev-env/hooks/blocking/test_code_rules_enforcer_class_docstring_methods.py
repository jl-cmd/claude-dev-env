"""Tests for check_class_docstring_names_public_methods — class prose breadth.

A class whose docstring is a single summary line names one responsibility. When
the class exposes a second public entry point the summary never names, the prose
under-describes the class — the same drift the os_update_workflow break reporter
hit when it grew a regular-pace method beside its coffee-break method.
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


def check_class_docstring_names_public_methods(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_class_docstring_names_public_methods(content, file_path)


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/break_reporter.py"
TEST_FILE_PATH = "/project/src/test_break_reporter.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _narrow_class_with_widened_surface() -> str:
    return (
        "class ConsoleBreakReporter:\n"
        '    """Run a coffee break with operator visibility: announce, then count down."""\n'
        "\n"
        "    async def pause_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
        "\n"
        "    async def stretch_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
    )


def test_should_flag_single_line_docstring_omitting_two_public_methods() -> None:
    issues = check_class_docstring_names_public_methods(
        _narrow_class_with_widened_surface(), PRODUCTION_FILE_PATH
    )
    assert any("pause_then_resume" in each for each in issues), (
        f"Expected omitted-method flag, got: {issues!r}"
    )
    assert any("stretch_then_resume" in each for each in issues)
    assert len(issues) == 1


def test_should_not_flag_when_summary_names_every_public_method() -> None:
    source = (
        "class ConsoleBreakReporter:\n"
        '    """Announce a pause then resume, or stretch then resume, with a countdown."""\n'
        "\n"
        "    async def pause_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
        "\n"
        "    async def stretch_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
    )
    issues = check_class_docstring_names_public_methods(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Summary naming every method must not flag, got: {issues!r}"


def test_should_not_flag_when_only_one_public_method_is_omitted() -> None:
    source = (
        "class ConsoleBreakReporter:\n"
        '    """Pause then resume the submission run with an operator countdown."""\n'
        "\n"
        "    async def pause_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
        "\n"
        "    async def stretch_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
    )
    issues = check_class_docstring_names_public_methods(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"A single omitted method must not flag, got: {issues!r}"


def test_should_not_flag_multi_line_docstring_body() -> None:
    source = (
        "class ConsoleBreakReporter:\n"
        '    """Run a coffee break with operator visibility.\n'
        "\n"
        "    Also paces the regular between-theme waits through the same seam.\n"
        '    """\n'
        "\n"
        "    async def pause_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
        "\n"
        "    async def stretch_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
    )
    issues = check_class_docstring_names_public_methods(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Multi-line docstrings go to the audit lane, got: {issues!r}"


def test_should_not_flag_class_with_single_public_method() -> None:
    source = (
        "class ConsoleBreakReporter:\n"
        '    """Run a coffee break with operator visibility."""\n'
        "\n"
        "    async def pause_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
    )
    issues = check_class_docstring_names_public_methods(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"A one-method class must not flag, got: {issues!r}"


def test_should_skip_private_methods_when_counting_surface() -> None:
    source = (
        "class ConsoleBreakReporter:\n"
        '    """Run a coffee break with operator visibility."""\n'
        "\n"
        "    async def pause_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
        "\n"
        "    async def _sleep(self, seconds: float) -> None:\n"
        "        await self._clock.sleep(seconds)\n"
        "\n"
        "    def __init__(self) -> None:\n"
        "        self._clock = None\n"
    )
    issues = check_class_docstring_names_public_methods(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Private and dunder methods are not public surface, got: {issues!r}"


def test_should_skip_class_without_docstring() -> None:
    source = (
        "class ConsoleBreakReporter:\n"
        "    async def pause_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
        "\n"
        "    async def stretch_then_resume(self, seconds: float) -> None:\n"
        "        await self._sleep(seconds)\n"
    )
    issues = check_class_docstring_names_public_methods(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"No-docstring classes are out of scope, got: {issues!r}"


def test_should_skip_test_file() -> None:
    issues = check_class_docstring_names_public_methods(
        _narrow_class_with_widened_surface(), TEST_FILE_PATH
    )
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_class_docstring_names_public_methods(
        _narrow_class_with_widened_surface(), HOOK_INFRASTRUCTURE_PATH
    )
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_class_docstring_names_public_methods("class Broken(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def _real_break_reporter_drift() -> str:
    return (
        "class ConsoleBreakReporter:\n"
        '    """Run a coffee-break with operator visibility: announce, then count down."""\n'
        "\n"
        "    async def announce_and_pause(self, nominal_break_seconds: float) -> None:\n"
        "        await self._announce(nominal_break_seconds)\n"
        "\n"
        "    async def announce_and_pause_exact(self, break_seconds: float) -> None:\n"
        "        await self._announce(break_seconds)\n"
    )


def test_should_flag_real_break_reporter_widened_surface() -> None:
    issues = check_class_docstring_names_public_methods(
        _real_break_reporter_drift(), PRODUCTION_FILE_PATH
    )
    assert any("announce_and_pause_exact" in each for each in issues), (
        f"Expected the regular-pace method to flag, got: {issues!r}"
    )
    assert any("announce_and_pause" in each for each in issues)
    assert len(issues) == 1


def test_validate_content_surfaces_class_docstring_breadth_drift() -> None:
    issues = validate_content(
        _narrow_class_with_widened_surface(), PRODUCTION_FILE_PATH, old_content=""
    )
    matching_issues = [
        each for each in issues if "pause_then_resume" in each and "public method" in each
    ]
    assert matching_issues, (
        f"Expected validate_content to surface the class-breadth drift, got: {issues!r}"
    )
