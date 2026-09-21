"""Tests for the shared constants this directory's test-support module provides."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from code_rules_enforcer_test_support import STRIP_CODE_AND_QUOTES_SOURCE


def should_define_a_strip_code_and_quotes_function_that_removes_fenced_code() -> None:
    module_namespace: dict[str, object] = {}
    exec(STRIP_CODE_AND_QUOTES_SOURCE, module_namespace)
    strip_code_and_quotes = cast("Callable[[str], str]", module_namespace["strip_code_and_quotes"])

    stripped = strip_code_and_quotes("keep this\n```\ncode block\n```\n> a quote\nkeep this too")

    assert "code block" not in stripped
    assert "a quote" not in stripped
    assert "keep this" in stripped
    assert "keep this too" in stripped
