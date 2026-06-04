"""Regression guard pinning docstring prose in code_rules_constants_config."""

from __future__ import annotations

import sys
from pathlib import Path

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_magic_values import check_magic_values  # noqa: E402


def test_module_source_carries_no_docstring_magic_value() -> None:
    module_path = Path(__file__).resolve().parent / "code_rules_constants_config.py"
    module_source = module_path.read_text(encoding="utf-8")
    magic_value_issues = check_magic_values(module_source, str(module_path))
    assert magic_value_issues == [], (
        "Docstring prose in code_rules_constants_config.py must not carry a "
        "bare-number token that the magic-value check flags as a literal, "
        f"got: {magic_value_issues}"
    )
