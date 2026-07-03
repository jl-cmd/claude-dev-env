"""Behavior tests for the code_rules_magic_values check module.

A diagram-first docstring may carry a bare number on an illustrative row
(``at line 2``). That number is prose, not a code literal, so the magic-value
check skips docstring rows while still flagging a real magic number in an
actual code statement.
"""

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

PRODUCTION_FILE_PATH = "packages/app/rendering.py"


def test_magic_value_check_skips_bare_number_inside_docstring_illustration() -> None:
    source = (
        "def summarize(record):\n"
        '    """Summarize how a run ended.\n'
        "\n"
        "    A finished run shows a clean outcome::\n"
        "\n"
        "        marked in-flight at row 2\n"
        '    """\n'
        "    return record\n"
    )
    issues = check_magic_values(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Expected no magic-value issue on an illustrative row, got: {issues}"


def test_magic_value_check_still_flags_real_magic_number_in_code_statement() -> None:
    source = (
        "def summarize(record):\n"
        '    """Summarize how a run ended.\n'
        "\n"
        "        marked in-flight at row 2\n"
        '    """\n'
        "    threshold = record.score * 42\n"
        "    return threshold\n"
    )
    issues = check_magic_values(source, PRODUCTION_FILE_PATH)
    assert any(issue.endswith("Magic value 42 - extract to named constant") for issue in issues), (
        f"Expected the real magic number 42 to stay flagged, got: {issues}"
    )
