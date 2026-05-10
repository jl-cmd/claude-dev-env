"""Tests for check_stub_implementations — flags placeholder function bodies.

Per Plan 1c.stub_detector / Phase B1: production functions whose body is
only `pass`, `...` (Ellipsis), or `raise NotImplementedError` are stubs.
Exemptions: ABC methods, Protocol methods, abstractmethod-decorated
functions, test files, hook infrastructure.
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


def check_stub_implementations(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_stub_implementations(content, file_path)

PRODUCTION_FILE_PATH = "/project/src/services.py"
TEST_FILE_PATH = "/project/src/test_services.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def test_should_flag_pass_only_function() -> None:
    source = "def parse_invoice(payload: str) -> int:\n    pass\n"
    issues = check_stub_implementations(source, PRODUCTION_FILE_PATH)
    assert any("parse_invoice" in each for each in issues), (
        f"Expected pass-only function to be flagged, got: {issues!r}"
    )


def test_should_flag_ellipsis_only_function() -> None:
    source = "def parse_invoice(payload: str) -> int:\n    ...\n"
    issues = check_stub_implementations(source, PRODUCTION_FILE_PATH)
    assert any("parse_invoice" in each for each in issues), (
        f"Expected ellipsis-only function to be flagged, got: {issues!r}"
    )


def test_should_flag_raise_not_implemented_function() -> None:
    source = "def parse_invoice(payload: str) -> int:\n    raise NotImplementedError\n"
    issues = check_stub_implementations(source, PRODUCTION_FILE_PATH)
    assert any("parse_invoice" in each for each in issues), (
        f"Expected NotImplementedError stub to be flagged, got: {issues!r}"
    )


def test_should_flag_raise_not_implemented_with_message() -> None:
    source = (
        "def parse_invoice(payload: str) -> int:\n"
        "    raise NotImplementedError('coming soon')\n"
    )
    issues = check_stub_implementations(source, PRODUCTION_FILE_PATH)
    assert any("parse_invoice" in each for each in issues), (
        f"Expected NotImplementedError(...) stub to be flagged, got: {issues!r}"
    )


def test_should_not_flag_function_with_docstring_then_pass() -> None:
    source = (
        "def parse_invoice(payload: str) -> int:\n"
        '    """Parse the invoice."""\n'
        "    pass\n"
    )
    issues = check_stub_implementations(source, PRODUCTION_FILE_PATH)
    assert any("parse_invoice" in each for each in issues), (
        f"Docstring + pass is still a stub; should be flagged. Got: {issues!r}"
    )


def test_should_not_flag_real_implementation() -> None:
    source = "def parse_invoice(payload: str) -> int:\n    return len(payload)\n"
    issues = check_stub_implementations(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Real impl must not be flagged, got: {issues!r}"


def test_should_exempt_abstractmethod_decorated() -> None:
    source = (
        "from abc import ABC, abstractmethod\n"
        "class InvoiceParser(ABC):\n"
        "    @abstractmethod\n"
        "    def parse(self, payload: str) -> int:\n"
        "        pass\n"
    )
    issues = check_stub_implementations(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"@abstractmethod must be exempt, got: {issues!r}"


def test_should_exempt_protocol_methods() -> None:
    source = (
        "from typing import Protocol\n"
        "class InvoiceParser(Protocol):\n"
        "    def parse(self, payload: str) -> int:\n"
        "        ...\n"
    )
    issues = check_stub_implementations(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Protocol methods must be exempt, got: {issues!r}"


def test_should_skip_test_file() -> None:
    source = "def stub_helper():\n    pass\n"
    issues = check_stub_implementations(source, TEST_FILE_PATH)
    assert issues == [], f"Test files must be exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    source = "def stub_helper():\n    pass\n"
    issues = check_stub_implementations(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Hook infrastructure must be exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    source = "def parse_invoice(\n"
    issues = check_stub_implementations(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax errors must yield no issues, got: {issues!r}"


def test_should_include_line_number_in_issue() -> None:
    source = "x = 1\n\ndef parse_invoice():\n    pass\n"
    issues = check_stub_implementations(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "Line 3" in issues[0], f"Issue must include line number, got: {issues[0]!r}"


def test_should_cap_at_three_issues() -> None:
    source = "\n\n".join(f"def stub_{i}():\n    pass" for i in range(5)) + "\n"
    issues = check_stub_implementations(source, PRODUCTION_FILE_PATH)
    assert len(issues) <= 3, f"Issue count must be capped at 3, got: {len(issues)}"
