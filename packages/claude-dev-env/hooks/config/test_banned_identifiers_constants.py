"""Behavior tests for banned-identifier configuration constants."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from config.banned_identifiers_constants import (
    ALL_BANNED_IDENTIFIERS,
    BANNED_IDENTIFIER_MESSAGE_SUFFIX,
    BANNED_IDENTIFIER_SKIP_ADVISORY,
    MAX_BANNED_IDENTIFIER_ISSUES,
)


def test_all_banned_identifiers_includes_canonical_offenders() -> None:
    canonical_offenders = {
        "result",
        "data",
        "output",
        "response",
        "value",
        "item",
        "temp",
        "argv",
        "args",
        "kwargs",
        "argc",
    }
    assert canonical_offenders <= ALL_BANNED_IDENTIFIERS


def test_max_banned_identifier_issues_is_positive_cap() -> None:
    assert MAX_BANNED_IDENTIFIER_ISSUES > 0


def test_banned_identifier_message_suffix_references_naming_section() -> None:
    assert "CODE_RULES" in BANNED_IDENTIFIER_MESSAGE_SUFFIX
    assert "Naming" in BANNED_IDENTIFIER_MESSAGE_SUFFIX


def test_banned_identifier_skip_advisory_explains_skip_reason() -> None:
    assert "skipped" in BANNED_IDENTIFIER_SKIP_ADVISORY
    assert "parse" in BANNED_IDENTIFIER_SKIP_ADVISORY
