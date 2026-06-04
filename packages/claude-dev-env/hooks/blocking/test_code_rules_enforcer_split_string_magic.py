"""Behavior tests for the code_rules_string_magic code-rules check module."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_string_magic import (  # noqa: E402
    check_inline_literal_collections,
    check_string_literal_magic,
)

code_rules_enforcer = SimpleNamespace(
    check_inline_literal_collections=check_inline_literal_collections,
    check_string_literal_magic=check_string_literal_magic,
)


INLINE_LITERAL_PRODUCTION_FILE_PATH = "packages/app/services/inline_literal.py"

STRING_MAGIC_PRODUCTION_FILE_PATH = "packages/app/services/string_magic.py"


def test_check_inline_literal_collections_flags_three_string_set_in_function() -> None:
    source = (
        "def is_known(value: str) -> bool:\n"
        "    return value in {'true', 'false', 'none'}\n"
    )
    issues = code_rules_enforcer.check_inline_literal_collections(
        source, INLINE_LITERAL_PRODUCTION_FILE_PATH
    )
    assert len(issues) == 1, f"Expected 3-element string set flagged, got: {issues}"


def test_check_string_literal_magic_flags_env_var_name() -> None:
    source = (
        "import os\n"
        "\n"
        "def fetch_secret() -> str:\n"
        "    return os.environ['STRIPE_SECRET']\n"
    )
    issues = code_rules_enforcer.check_string_literal_magic(
        source, STRING_MAGIC_PRODUCTION_FILE_PATH
    )
    assert any("STRIPE_SECRET" in each_issue for each_issue in issues), (
        f"Expected env-var name flagged, got: {issues}"
    )
