"""Tests for unused module import constants."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from config.unused_module_import_constants import line_suppresses_unused_import_via_noqa


def test_line_suppresses_bare_noqa() -> None:
    assert line_suppresses_unused_import_via_noqa(
        "from x import y  # noqa"
    )


def test_line_suppresses_noqa_with_f401_code() -> None:
    assert line_suppresses_unused_import_via_noqa(
        "from x import y  # noqa: F401"
    )


def test_line_suppresses_noqa_with_mixed_codes_including_f401() -> None:
    assert line_suppresses_unused_import_via_noqa(
        "from x import y  # noqa: E402, F401"
    )


def test_line_does_not_suppress_noqa_with_only_non_f401_codes() -> None:
    assert not line_suppresses_unused_import_via_noqa(
        "from x import y  # noqa: E402"
    )


def test_line_does_not_suppress_without_noqa() -> None:
    assert not line_suppresses_unused_import_via_noqa(
        "from x import y  # type: ignore"
    )


def test_line_does_not_suppress_noqa_inside_string_literal() -> None:
    assert not line_suppresses_unused_import_via_noqa(
        "from x import y; marker = '# noqa: F401'"
    )
