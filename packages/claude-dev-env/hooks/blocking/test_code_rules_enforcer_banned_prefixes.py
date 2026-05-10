"""Tests for check_banned_prefixes — flags function names with generic prefixes.

CODE_RULES.md §5 / AGENTS.md "Naming → Function names use specific verbs:
parse_invoice, dispatch_event, migrate_schema. Generic prefixes to replace:
handle_, process_, manage_, do_."

The check fires on def / async def names (functions and methods) in
production code, exempting test files and hook infrastructure.
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

PRODUCTION_FILE_PATH = "src/example_production.py"
TEST_FILE_PATH = "src/test_example.py"
HOOK_INFRASTRUCTURE_FILE_PATH = "/home/user/.claude/hooks/blocking/example_hook.py"


def test_should_flag_handle_prefixed_function() -> None:
    content = "def handle_request(payload):\n    return payload\n"
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert any("handle_request" in each_issue for each_issue in issues), (
        f"Expected 'handle_request' to be flagged, got: {issues!r}"
    )


def test_should_flag_process_prefixed_function() -> None:
    content = "def process_data(items):\n    return items\n"
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert any("process_data" in each_issue for each_issue in issues), (
        f"Expected 'process_data' to be flagged, got: {issues!r}"
    )


def test_should_flag_manage_prefixed_function() -> None:
    content = "def manage_session(session_id):\n    return session_id\n"
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert any("manage_session" in each_issue for each_issue in issues), (
        f"Expected 'manage_session' to be flagged, got: {issues!r}"
    )


def test_should_flag_do_prefixed_function() -> None:
    content = "def do_thing(argument):\n    return argument\n"
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert any("do_thing" in each_issue for each_issue in issues), (
        f"Expected 'do_thing' to be flagged, got: {issues!r}"
    )


def test_should_flag_async_function_with_banned_prefix() -> None:
    content = "async def handle_event(event):\n    return event\n"
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert any("handle_event" in each_issue for each_issue in issues), (
        f"Expected async 'handle_event' to be flagged, got: {issues!r}"
    )


def test_should_flag_method_with_banned_prefix() -> None:
    content = (
        "class OrderService:\n"
        "    def process_order(self, order):\n"
        "        return order\n"
    )
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert any("process_order" in each_issue for each_issue in issues), (
        f"Expected method 'process_order' to be flagged, got: {issues!r}"
    )


def test_should_not_flag_function_without_banned_prefix() -> None:
    content = "def parse_invoice(payload):\n    return payload\n"
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert issues == [], f"Expected no issues for 'parse_invoice', got: {issues!r}"


def test_should_not_flag_function_with_handle_substring_but_no_underscore() -> None:
    content = "def handler(payload):\n    return payload\n"
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"'handler' is a noun, not a banned 'handle_' prefix; got: {issues!r}"
    )


def test_should_not_flag_function_with_doctor_prefix() -> None:
    content = "def doctor_visit(patient):\n    return patient\n"
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"'doctor_visit' starts with 'do' but not 'do_'; got: {issues!r}"
    )


def test_should_skip_test_file() -> None:
    content = "def handle_request(payload):\n    return payload\n"
    issues = code_rules_enforcer.check_banned_prefixes(content, TEST_FILE_PATH)
    assert issues == [], f"Test files must be exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    content = "def handle_request(payload):\n    return payload\n"
    issues = code_rules_enforcer.check_banned_prefixes(
        content, HOOK_INFRASTRUCTURE_FILE_PATH
    )
    assert issues == [], f"Hook infrastructure must be exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    content = "def handle_request(\n"
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax errors must yield no issues, got: {issues!r}"


def test_should_include_line_number_and_function_name() -> None:
    content = "x = 1\n\ndef handle_event(event):\n    return event\n"
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1, f"Expected exactly one issue, got: {issues!r}"
    assert "Line 3" in issues[0], (
        f"Issue must include the line number, got: {issues[0]!r}"
    )
    assert "handle_event" in issues[0], (
        f"Issue must include the function name, got: {issues[0]!r}"
    )


def test_should_cap_at_three_issues() -> None:
    content = (
        "def handle_one():\n    pass\n"
        "def handle_two():\n    pass\n"
        "def handle_three():\n    pass\n"
        "def handle_four():\n    pass\n"
        "def handle_five():\n    pass\n"
    )
    issues = code_rules_enforcer.check_banned_prefixes(content, PRODUCTION_FILE_PATH)
    assert len(issues) <= 3, (
        f"Issue count must be capped at 3, got {len(issues)}: {issues!r}"
    )
