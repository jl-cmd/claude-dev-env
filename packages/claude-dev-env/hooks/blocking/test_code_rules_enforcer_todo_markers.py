"""Tests covering TODO/FIXME/HACK/XXX exemption from the comment blocker.

CODE_RULES.md requires scaffolding/placeholder code to carry TODO comments
naming what replaces it and why. Without an exemption, the no-NEW-comments
rule blocks every authored TODO. These tests pin the exemption.
"""

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

from code_rules_comments import (  # noqa: E402
    check_comments_javascript,
    check_comments_python,
    extract_comment_texts,
)

code_rules_enforcer = SimpleNamespace(
    check_comments_javascript=check_comments_javascript,
    check_comments_python=check_comments_python,
    extract_comment_texts=extract_comment_texts,
)


def test_python_check_should_exempt_standalone_todo_comment() -> None:
    content = "# TODO: replace stub with real implementation\nx = 1\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == [], f"Expected no issues for '# TODO:' but got: {issues!r}"


def test_python_check_should_exempt_standalone_fixme_comment() -> None:
    content = "# FIXME: handle the empty list case\nx = 1\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == [], f"Expected no issues for '# FIXME:' but got: {issues!r}"


def test_python_check_should_exempt_standalone_hack_comment() -> None:
    content = "# HACK: working around upstream bug #1234\nx = 1\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == [], f"Expected no issues for '# HACK:' but got: {issues!r}"


def test_python_check_should_exempt_standalone_xxx_comment() -> None:
    content = "# XXX revisit when API stabilizes\nx = 1\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == [], f"Expected no issues for '# XXX' but got: {issues!r}"


def test_python_check_should_exempt_inline_todo_comment() -> None:
    content = "x = 1  # TODO: extract to config\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == [], f"Expected no issues for inline TODO but got: {issues!r}"


def test_python_check_should_exempt_inline_fixme_comment() -> None:
    content = "x = 1  # FIXME: race condition\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == [], f"Expected no issues for inline FIXME but got: {issues!r}"


def test_javascript_check_should_exempt_inline_todo_comment() -> None:
    content = "const x = 1; // TODO: replace with config\n"
    issues = code_rules_enforcer.check_comments_javascript(content)
    assert issues == [], f"Expected no issues for JS inline TODO but got: {issues!r}"


def test_javascript_check_should_exempt_inline_fixme_comment() -> None:
    content = "const x = 1; // FIXME: handle null case\n"
    issues = code_rules_enforcer.check_comments_javascript(content)
    assert issues == [], f"Expected no issues for JS inline FIXME but got: {issues!r}"


def test_extract_comment_texts_should_skip_standalone_todo() -> None:
    content = "# TODO: replace stub\nx = 1\n"
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert "# TODO: replace stub" not in standalone, (
        "Standalone TODO must not be tracked as a comment subject to "
        f"deletion-blocking, got standalone={standalone!r}"
    )


def test_extract_comment_texts_should_skip_inline_todo() -> None:
    content = "x = 1  # TODO: extract to config\n"
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert all("TODO" not in each_comment for each_comment in inline), (
        "Inline TODO must not be tracked as a comment subject to "
        f"deletion-blocking, got inline={inline!r}"
    )


def test_existing_non_todo_comment_still_flagged() -> None:
    content = "x = 1  # this is just a comment\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert len(issues) == 1, (
        f"Expected non-TODO inline comment to still be flagged, got: {issues!r}"
    )
