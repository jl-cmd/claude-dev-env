"""Tests for check_typed_dict_encode_decode — flags TypedDicts missing companion encoders.

Per Plan 1c.typed_dict_validator / Phase B2: every TypedDict declaration in
production code must have a companion `_encode_<snake_name>` and
`_decode_<snake_name>` function so untyped dicts cannot leak across module
boundaries without explicit validation.
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


def check_typed_dict_encode_decode(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_typed_dict_encode_decode(content, file_path)


PRODUCTION_FILE_PATH = "/project/src/contracts.py"
TEST_FILE_PATH = "/project/src/test_contracts.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def test_should_flag_typed_dict_without_encode_or_decode() -> None:
    source = (
        "from typing import TypedDict\n"
        "class InvoicePayload(TypedDict):\n"
        "    amount: int\n"
    )
    issues = check_typed_dict_encode_decode(source, PRODUCTION_FILE_PATH)
    assert any("InvoicePayload" in each for each in issues), (
        f"Expected InvoicePayload to be flagged, got: {issues!r}"
    )


def test_should_flag_typed_dict_with_only_encode() -> None:
    source = (
        "from typing import TypedDict\n"
        "class InvoicePayload(TypedDict):\n"
        "    amount: int\n"
        "def _encode_invoice_payload(value: InvoicePayload) -> bytes:\n"
        "    return b''\n"
    )
    issues = check_typed_dict_encode_decode(source, PRODUCTION_FILE_PATH)
    assert any(
        "InvoicePayload" in each and "decode" in each.lower() for each in issues
    ), f"Expected missing _decode_ to be flagged, got: {issues!r}"


def test_should_flag_typed_dict_with_only_decode() -> None:
    source = (
        "from typing import TypedDict\n"
        "class InvoicePayload(TypedDict):\n"
        "    amount: int\n"
        "def _decode_invoice_payload(raw: bytes) -> InvoicePayload:\n"
        "    return {'amount': 0}\n"
    )
    issues = check_typed_dict_encode_decode(source, PRODUCTION_FILE_PATH)
    assert any(
        "InvoicePayload" in each and "encode" in each.lower() for each in issues
    ), f"Expected missing _encode_ to be flagged, got: {issues!r}"


def test_should_not_flag_typed_dict_with_both_companions() -> None:
    source = (
        "from typing import TypedDict\n"
        "class InvoicePayload(TypedDict):\n"
        "    amount: int\n"
        "def _encode_invoice_payload(value: InvoicePayload) -> bytes:\n"
        "    return b''\n"
        "def _decode_invoice_payload(raw: bytes) -> InvoicePayload:\n"
        "    return {'amount': 0}\n"
    )
    issues = check_typed_dict_encode_decode(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Both companions present, got: {issues!r}"


def test_should_handle_pascal_to_snake_conversion() -> None:
    source = (
        "from typing import TypedDict\n"
        "class TypedAuthRequest(TypedDict):\n"
        "    token: str\n"
    )
    issues = check_typed_dict_encode_decode(source, PRODUCTION_FILE_PATH)
    assert any("TypedAuthRequest" in each for each in issues), (
        f"PascalCase conversion expected; got: {issues!r}"
    )


def test_should_skip_test_file() -> None:
    source = "from typing import TypedDict\nclass MockPayload(TypedDict):\n    x: int\n"
    issues = check_typed_dict_encode_decode(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    source = "from typing import TypedDict\nclass HookPayload(TypedDict):\n    x: int\n"
    issues = check_typed_dict_encode_decode(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    source = "class InvoicePayload(TypedDict\n"
    issues = check_typed_dict_encode_decode(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_should_not_flag_non_typed_dict_class() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Invoice:\n"
        "    amount: int\n"
    )
    issues = check_typed_dict_encode_decode(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Regular dataclass must not be flagged, got: {issues!r}"
