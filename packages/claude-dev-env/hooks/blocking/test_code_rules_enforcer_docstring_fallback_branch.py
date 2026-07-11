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


def test_should_not_flag_when_scope_phrase_is_a_substring_of_another_word() -> None:
    source = (
        "def refresh(cache: object) -> None:\n"
        '    """Rebuild the cache; commonly when idle it reuses the warm copy."""\n'
        "    if cache is None:\n"
        "        rebuild_cache(None)\n"
        "        return\n"
        "    if cache.is_cold:\n"
        "        rebuild_cache(cache)\n"
        "        return\n"
        "    serve_cache(cache)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "'commonly when' must not match the 'only when' scope phrase as a bare "
        f"substring, got: {issues!r}"
    )


def test_should_still_flag_word_boundary_scope_phrase() -> None:
    source = (
        "def refresh(cache: object) -> None:\n"
        '    """Rebuild the cache only when it is invalid."""\n'
        "    if cache is None:\n"
        "        rebuild_cache(None)\n"
        "        return\n"
        "    if cache.is_cold:\n"
        "        rebuild_cache(cache)\n"
        "        return\n"
        "    serve_cache(cache)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert any("rebuild_cache" in each for each in issues), (
        f"A genuine 'only when' scope phrase must still be flagged, got: {issues!r}"
    )


def test_should_not_flag_when_summary_enumerates_both_conditions_inline() -> None:
    source = (
        "def scroll(bar: object) -> None:\n"
        '    """Drive a scrollbar pass, falling back to the keyboard when the bar'
        ' lacks geometry or on a random fraction of passes."""\n'
        "    if bar is None:\n"
        "        _keyboard(None)\n"
        "        return\n"
        "    if bar.is_random:\n"
        "        _keyboard(bar)\n"
        "        return\n"
        "    _drive(bar)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "A summary that enumerates both fallback conditions inline with 'or' is not "
        f"a single-condition scope and must not be flagged, got: {issues!r}"
    )


def test_should_still_flag_single_condition_fallback_with_two_routes() -> None:
    source = (
        "def scroll(bar: object) -> None:\n"
        '    """Drive a scrollbar pass, falling back to the keyboard when the bar'
        ' lacks geometry."""\n'
        "    if bar is None:\n"
        "        _keyboard(None)\n"
        "        return\n"
        "    if bar.is_random:\n"
        "        _keyboard(bar)\n"
        "        return\n"
        "    _drive(bar)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert any("_keyboard" in each for each in issues), (
        "A summary scoping the fallback to one named condition while two routes reach "
        f"it must still be flagged, got: {issues!r}"
    )


def test_should_not_flag_when_scope_phrase_is_a_left_anchored_prefix() -> None:
    source = (
        "def forward(packet: object) -> None:\n"
        '    """Forward the packet; falls back toward the default sink when both'
        ' checks miss."""\n'
        "    if packet is None:\n"
        "        send_to_sink(None)\n"
        "        return\n"
        "    if packet.is_stale:\n"
        "        send_to_sink(packet)\n"
        "        return\n"
        "    deliver(packet)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "'falls back toward' must not match the 'falls back to' scope phrase as a "
        f"left-anchored prefix, got: {issues!r}"
    )


def test_should_not_flag_only_whenever_left_anchored_prefix() -> None:
    source = (
        "def refresh(cache: object) -> None:\n"
        '    """Rebuild the cache only whenever it is invalid or stale."""\n'
        "    if cache is None:\n"
        "        rebuild_cache(None)\n"
        "        return\n"
        "    if cache.is_cold:\n"
        "        rebuild_cache(cache)\n"
        "        return\n"
        "    serve_cache(cache)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "'only whenever' must not match the 'only when' scope phrase as a "
        f"left-anchored prefix, got: {issues!r}"
    )


def test_should_not_flag_two_branches_to_same_method_on_distinct_indexed_receivers() -> None:
    source = (
        "class Pool:\n"
        "    def shutdown(self, signal: object) -> None:\n"
        '        """Close resources only when a shutdown signal arrives."""\n'
        "        if signal is None:\n"
        "            self.pool[0].close(signal)\n"
        "            return\n"
        "        if signal.is_secondary:\n"
        "            self.pool[1].close(signal)\n"
        "            return\n"
        "        self.pool[2].drain(signal)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "Distinct indexed receivers calling the same method name are different "
        f"fallbacks, got: {issues!r}"
    )


def test_should_not_flag_two_branches_to_same_named_method_on_distinct_receivers() -> None:
    source = (
        "class Closer:\n"
        "    def shutdown(self, signal: object) -> None:\n"
        '        """Close resources only when a shutdown signal arrives."""\n'
        "        if signal is None:\n"
        "            self.primary.close(signal)\n"
        "            return\n"
        "        if signal.is_secondary:\n"
        "            self.secondary.close(signal)\n"
        "            return\n"
        "        self.tertiary.close(signal)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "Distinct receivers calling the same method name are different fallbacks, "
        f"got: {issues!r}"
    )


def test_should_flag_two_branches_to_same_method_on_one_receiver() -> None:
    source = (
        "class Closer:\n"
        "    def shutdown(self, signal: object) -> None:\n"
        '        """Close resources only when a shutdown signal arrives."""\n'
        "        if signal is None:\n"
        "            self.primary.close(signal)\n"
        "            return\n"
        "        if signal.is_secondary:\n"
        "            self.primary.close(signal)\n"
        "            return\n"
        "        self.primary.drain(signal)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert any("self.primary.close" in each for each in issues), (
        f"Two routes to the same receiver.method must be flagged, got: {issues!r}"
    )


def test_should_flag_multi_statement_guard_with_one_call_before_return() -> None:
    source = (
        "def select(target: object) -> None:\n"
        '    """Pick a candidate, falling back to the press action when idle."""\n'
        "    if target is None:\n"
        "        attempt = 1\n"
        "        _press(None)\n"
        "        return\n"
        "    if target.is_idle:\n"
        "        attempt = 1\n"
        "        _press(target)\n"
        "        return\n"
        "    _drive(target)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert any("_press" in each for each in issues), (
        "A guard with a non-call statement before its single call still routes "
        f"to that call, got: {issues!r}"
    )


def test_should_not_flag_guard_with_a_second_call_expression() -> None:
    source = (
        "def select(target: object) -> None:\n"
        '    """Pick a candidate, falling back to the press action when idle."""\n'
        "    if target is None:\n"
        "        _press(None)\n"
        "        _press(None)\n"
        "        return\n"
        "    if target.is_idle:\n"
        "        _press(target)\n"
        "        _press(target)\n"
        "        return\n"
        "    _drive(target)\n"
    )
    issues = check_docstring_fallback_branch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A second call expression disqualifies the block as a route, got: {issues!r}"
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
