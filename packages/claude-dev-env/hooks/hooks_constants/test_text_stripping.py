"""Tests for the shared strip_code_and_quotes helper."""

import pathlib
import sys

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.text_stripping import strip_code_and_quotes


def test_removes_fenced_code_block() -> None:
    text = "before\n```python\nshould I run this?\n```\nafter"
    stripped = strip_code_and_quotes(text)
    assert "should I run this?" not in stripped
    assert "before" in stripped
    assert "after" in stripped


def test_removes_inline_code_span() -> None:
    text = "the function `would you like` is named oddly"
    stripped = strip_code_and_quotes(text)
    assert "would you like" not in stripped
    assert "the function" in stripped
    assert "is named oddly" in stripped


def test_removes_leading_blockquote_lines() -> None:
    text = "real line\n> should I proceed?\nfinal line"
    stripped = strip_code_and_quotes(text)
    assert "should I proceed?" not in stripped
    assert "real line" in stripped
    assert "final line" in stripped


def test_leaves_plain_prose_unchanged() -> None:
    text = "This sentence carries no code or quotes."
    assert strip_code_and_quotes(text) == text
