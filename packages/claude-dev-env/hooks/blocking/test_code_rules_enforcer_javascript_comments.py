"""Tests for JavaScript comment extraction and diff occurrence reporting."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

comment_rules_module = importlib.import_module("code_rules_comments")
check_comment_changes = comment_rules_module.check_comment_changes
code_rules_enforcer_module = importlib.import_module("code_rules_enforcer")


def test_check_comment_changes_ignores_javascript_url_string() -> None:
    issues = check_comment_changes(
        "", 'const docsUrl = "https://example.com/guide";\n', "docs.js"
    )

    assert issues == []


def test_check_comment_changes_reports_javascript_comment_line() -> None:
    issues = check_comment_changes(
        "", 'const total = 1;\nconst next = 2; // added\n', "totals.js"
    )

    assert any("Line 2: Inline comment added" in each_issue for each_issue in issues)


def test_check_comment_changes_reports_duplicate_identical_comment_occurrence() -> None:
    issues = check_comment_changes(
        "total = 1  # repeated\n",
        "total = 1  # repeated\ntotal = 2  # repeated\n",
        "totals.py",
    )

    assert any("Line 2: Inline comment added" in each_issue for each_issue in issues)


def test_check_comment_changes_does_not_match_comment_text_inside_changed_string() -> None:
    issues = check_comment_changes(
        "# note\n\ntotal = 1\n",
        '"# note"\ntotal = 2\n',
        "totals.py",
    )

    assert not any("still on the changed lines" in each_issue for each_issue in issues)


def test_check_comment_changes_flags_comment_attached_to_deleted_code() -> None:
    issues = check_comment_changes(
        "# attached\nold_total = 1\nnew_total = 2\n",
        "# attached\nnew_total = 2\n",
        "totals.py",
    )

    assert any("Standalone comment still on the changed lines" in each_issue for each_issue in issues)


def test_check_comment_changes_maps_identical_comments_to_equal_lines() -> None:
    old_content = "# duplicate\nold_total = 1\n# duplicate\nlater_total = 2\n"
    new_content = "# duplicate\nlater_total = 2\n"

    issues = check_comment_changes(old_content, new_content, "totals.py")

    assert not any("still on the changed lines" in each_issue for each_issue in issues)


def test_full_gate_is_comment_neutral_by_default() -> None:
    issues = code_rules_enforcer_module.validate_content_for_full_gate(
        "total = 1  # added\n",
        "totals.py",
        "total = 1\n",
    )

    assert not any("comment" in each_issue.lower() for each_issue in issues)
