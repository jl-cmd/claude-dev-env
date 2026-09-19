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


ARCHIVED_USE_COUNT_CHECK_NAME = "check_file_global_constants_use_count"


def test_module_defines_no_check_for_an_archived_rule() -> None:
    module_path = Path(__file__).resolve().parent / "code_rules_constants_config.py"
    module_source = module_path.read_text(encoding="utf-8")
    assert ARCHIVED_USE_COUNT_CHECK_NAME not in module_source, (
        "The file-global constant use-count rule was retired, so this "
        "module must define no check that enforces it. Code left behind keeps "
        "enforcing a rule the package no longer documents."
    )
