"""Behavior tests for the code_rules_comments code-rules check module."""

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
    check_comments_python,
)

code_rules_enforcer = SimpleNamespace(
    check_comments_python=check_comments_python,
)


def test_exempt_comment_rejects_noqa_prefixed_prose_lacking_boundary() -> None:
    """A comment body that merely starts with `noqa` followed by non-boundary
    characters is not a real noqa directive and must stay subject to the
    no-new-comments rule."""
    source = "x = compute()  # noqa-but-not-really: explanation\n"
    issues = code_rules_enforcer.check_comments_python(source)
    assert issues


def test_exempt_comment_keeps_bare_and_coded_noqa_exempt() -> None:
    """A bare `# noqa` and a coded `# noqa: E501` remain exempt under the
    tightened boundary rule."""
    bare_source = "x = compute()  # noqa\n"
    coded_source = "x = compute()  # noqa: E501\n"
    assert code_rules_enforcer.check_comments_python(bare_source) == []
    assert code_rules_enforcer.check_comments_python(coded_source) == []


def test_exempt_comment_keeps_colon_terminated_markers_without_trailing_space() -> None:
    """A colon-terminated marker (`pylint:`, `type:`, `pragma:`) is self-bounded
    by its own colon, so the directive stays exempt even when the next character
    follows the colon immediately."""
    pylint_source = "import os  # pylint:disable=unused-import\n"
    type_ignore_source = "x = compute()  # type:ignore\n"
    pragma_source = "x = compute()  # pragma:no-cover\n"
    assert code_rules_enforcer.check_comments_python(pylint_source) == []
    assert code_rules_enforcer.check_comments_python(type_ignore_source) == []
    assert code_rules_enforcer.check_comments_python(pragma_source) == []


def test_exempt_comment_still_flags_noqa_glued_to_prose_without_boundary() -> None:
    """The colon-terminated allowance must not loosen the boundary rule for
    markers that do not end in a colon: `# noqaFOO` still lacks a real boundary
    after `noqa` and stays subject to the no-new-comments rule."""
    source = "x = compute()  # noqaFOO\n"
    assert code_rules_enforcer.check_comments_python(source)
