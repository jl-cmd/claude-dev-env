"""Tests for check_docstring_fallback_branch_coverage — O6 fallback-branch drift.

A function whose summary scopes a fallback to one condition while the body
routes to that same fallback call from two or more distinct early-return guards
hides the second condition from the reader. This is the deterministic slice of
Category O6 (docstring prose vs implementation drift).
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


def check_docstring_fallback_branch_coverage(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_fallback_branch_coverage(content, file_path)


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/human_actions.py"
TEST_FILE_PATH = "/project/src/test_human_actions.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _drifted_scroll_method() -> str:
    return (
        "class HumanActions:\n"
        "    async def _scroll_once_toward_target(\n"
        "        self, all_container_screen_bounds: object\n"
        "    ) -> None:\n"
        '        """Drive one scrollbar pass, falling back to the keyboard when'
        ' the bar has no geometry."""\n'
        "        if all_container_screen_bounds is None:\n"
        "            await self._activate_then_press_right_arrow(None)\n"
        "            return\n"
        "        if random.random() < wheel_scroll_config.keyboard_scroll_fallback_probability:\n"
        "            await self._activate_then_press_right_arrow(all_container_screen_bounds)\n"
        "            return\n"
        "        await self._drive_scrollbar_gesture(all_container_screen_bounds)\n"
    )


def _enumerated_scroll_method() -> str:
    return (
        "class HumanActions:\n"
        "    async def _scroll_once_toward_target(\n"
        "        self, all_container_screen_bounds: object\n"
        "    ) -> None:\n"
        '        """Drive one scrollbar pass.\n'
        "\n"
        "        Route to the Right-Arrow keyboard burst either when the bar has\n"
        "        no geometry or, on a random keyboard_scroll_fallback_probability\n"
        "        fraction of passes, when geometry is available.\n"
        '        """\n'
        "        if all_container_screen_bounds is None:\n"
        "            await self._activate_then_press_right_arrow(None)\n"
        "            return\n"
        "        if random.random() < wheel_scroll_config.keyboard_scroll_fallback_probability:\n"
        "            await self._activate_then_press_right_arrow(all_container_screen_bounds)\n"
        "            return\n"
        "        await self._drive_scrollbar_gesture(all_container_screen_bounds)\n"
    )


def test_should_flag_two_branches_routing_to_one_scoped_fallback() -> None:
    issues = check_docstring_fallback_branch_coverage(
        _drifted_scroll_method(), PRODUCTION_FILE_PATH
    )
    assert any("_activate_then_press_right_arrow" in each for each in issues), (
        f"Expected the second fallback route to be flagged, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_report_the_route_count_in_the_message() -> None:
    issues = check_docstring_fallback_branch_coverage(
        _drifted_scroll_method(), PRODUCTION_FILE_PATH
    )
    assert any("2 distinct branches" in each for each in issues), (
        f"Expected the branch count in the message, got: {issues!r}"
    )


def test_should_not_flag_when_both_conditions_are_enumerated() -> None:
    issues = check_docstring_fallback_branch_coverage(
        _enumerated_scroll_method(), PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"A docstring that enumerates both routes must not be flagged, got: {issues!r}"
    )


def test_should_not_flag_single_branch_fallback() -> None:
    source = (
        "def render(view: object) -> str:\n"
        '    """Render the view, falling back to the empty string when absent."""\n'
        "    if view is None:\n"
        "        return ''\n"
        "    return view.body\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"One fallback route under one named condition is correct, got: {issues!r}"


def test_should_not_flag_two_branches_to_different_callees() -> None:
    source = (
        "def dispatch(event: object) -> None:\n"
        '    """Dispatch the event, falling back to the logger when unroutable."""\n'
        "    if event is None:\n"
        "        log_warning('empty')\n"
        "        return\n"
        "    if event.is_stale:\n"
        "        drop_event(event)\n"
        "        return\n"
        "    route_event(event)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Distinct callees per branch are not a shared-fallback drift, got: {issues!r}"
    )


def test_should_not_flag_when_docstring_has_no_scope_phrase() -> None:
    source = (
        "def select(target: object) -> None:\n"
        '    """Pick the first matching candidate from the registry."""\n'
        "    if target is None:\n"
        "        await _press(None)\n"
        "        return\n"
        "    if target.is_idle:\n"
        "        await _press(target)\n"
        "        return\n"
        "    await _drive(target)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"No exclusive-scope phrase means no fallback claim to check, got: {issues!r}"
    )


def test_should_skip_test_file() -> None:
    issues = check_docstring_fallback_branch_coverage(_drifted_scroll_method(), TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_docstring_fallback_branch_coverage(
        _drifted_scroll_method(), HOOK_INFRASTRUCTURE_PATH
    )
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_docstring_fallback_branch_coverage("def fetch(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_validate_content_surfaces_fallback_branch_drift() -> None:
    issues = validate_content(_drifted_scroll_method(), PRODUCTION_FILE_PATH, old_content="")
    matching_issues = [
        each for each in issues if "_activate_then_press_right_arrow" in each and "O6" in each
    ]
    assert matching_issues, (
        f"Expected validate_content to surface the O6 fallback-branch drift, got: {issues!r}"
    )
