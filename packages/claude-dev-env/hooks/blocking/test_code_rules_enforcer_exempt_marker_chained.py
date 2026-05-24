"""Tests for token-anchored exempt-marker behavior in `_is_exempt_python_comment`.

A bare ``#`` appearing after a token-anchored exempt marker (``noqa``,
``pylint:``, ``pragma:``) marks the trailing text as a separate inline comment
that the no-new-comments rule must catch. The chained ``#`` triggers detection
whether or not it carries surrounding whitespace — glued directly to the
directive (``# noqa: F401#note``), lacking a trailing space (``# noqa: F401
#prose``), or padded on both sides (``# noqa: F401  # prose``) all fire.
Free-form markers (``type:``, ``TODO``, ``FIXME``, ``HACK``, ``XXX``) keep their
permissive behavior because ``# type:`` participates in the justification
convention enforced by ``check_type_escape_hatches`` and the TODO-family markers
carry annotation text by convention.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tokenize

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIR / "code_rules_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
_is_exempt_python_comment = hook_module._is_exempt_python_comment
check_comments_python = hook_module.check_comments_python


FIXTURE_INLINE_COMMENT_LINE = 5
FIXTURE_INLINE_COMMENT_COLUMN = 4


def _build_comment_token(comment_text: str) -> tokenize.TokenInfo:
    return tokenize.TokenInfo(
        type=tokenize.COMMENT,
        string=comment_text,
        start=(FIXTURE_INLINE_COMMENT_LINE, FIXTURE_INLINE_COMMENT_COLUMN),
        end=(FIXTURE_INLINE_COMMENT_LINE, FIXTURE_INLINE_COMMENT_COLUMN + len(comment_text)),
        line=comment_text + "\n",
    )


def test_should_exempt_bare_noqa_directive() -> None:
    token = _build_comment_token("# noqa: F401")
    assert _is_exempt_python_comment(token) is True


def test_should_flag_noqa_with_chained_inline_comment() -> None:
    token = _build_comment_token("# noqa: F401  # imported for re-export")
    assert _is_exempt_python_comment(token) is False


def test_should_flag_noqa_prefixed_prose_lacking_token_boundary() -> None:
    token = _build_comment_token("# noqa-but-not-really: explanation")
    assert _is_exempt_python_comment(token) is False


def test_should_exempt_bare_noqa_without_code() -> None:
    token = _build_comment_token("# noqa")
    assert _is_exempt_python_comment(token) is True


def test_should_exempt_noqa_followed_by_whitespace_then_code() -> None:
    token = _build_comment_token("# noqa F401")
    assert _is_exempt_python_comment(token) is True


def test_should_flag_noqa_with_chained_hash_glued_directly_to_directive() -> None:
    token = _build_comment_token("# noqa: F401#note")
    assert _is_exempt_python_comment(token) is False


def test_should_flag_noqa_with_chained_hash_lacking_trailing_space() -> None:
    token = _build_comment_token("# noqa: F401 #prose")
    assert _is_exempt_python_comment(token) is False


def test_should_flag_pragma_with_chained_hash_glued_directly_to_directive() -> None:
    token = _build_comment_token("# pragma: no cover#why")
    assert _is_exempt_python_comment(token) is False


def test_should_flag_pylint_with_chained_hash_lacking_trailing_space() -> None:
    token = _build_comment_token("# pylint: disable=line-too-long #prose")
    assert _is_exempt_python_comment(token) is False


def test_should_exempt_bare_pylint_directive() -> None:
    token = _build_comment_token("# pylint: disable=line-too-long")
    assert _is_exempt_python_comment(token) is True


def test_should_flag_pylint_with_chained_inline_comment() -> None:
    token = _build_comment_token("# pylint: disable=line-too-long  # see SO answer")
    assert _is_exempt_python_comment(token) is False


def test_should_exempt_pylint_directive_without_space_after_colon() -> None:
    token = _build_comment_token("# pylint:disable=unused-import")
    assert _is_exempt_python_comment(token) is True


def test_should_exempt_pragma_directive_without_space_after_colon() -> None:
    token = _build_comment_token("# pragma:no-cover")
    assert _is_exempt_python_comment(token) is True


def test_should_exempt_type_ignore_without_space_after_colon() -> None:
    token = _build_comment_token("# type:ignore")
    assert _is_exempt_python_comment(token) is True


def test_should_flag_noqa_glued_prose_lacking_real_boundary() -> None:
    token = _build_comment_token("# noqaFOO")
    assert _is_exempt_python_comment(token) is False


def test_should_exempt_bare_pragma_directive() -> None:
    token = _build_comment_token("# pragma: no cover")
    assert _is_exempt_python_comment(token) is True


def test_should_flag_pragma_with_chained_inline_comment() -> None:
    token = _build_comment_token("# pragma: no cover  # only exercised in nightly")
    assert _is_exempt_python_comment(token) is False


def test_should_still_exempt_type_ignore_with_trailing_justification() -> None:
    token = _build_comment_token("# type: ignore[misc]  # stubs missing in foo library")
    assert _is_exempt_python_comment(token) is True


def test_should_exempt_bare_type_ignore_directive() -> None:
    token = _build_comment_token("# type: ignore")
    assert _is_exempt_python_comment(token) is True


def test_should_exempt_todo_with_trailing_prose() -> None:
    token = _build_comment_token("# TODO: rename after deprecation period")
    assert _is_exempt_python_comment(token) is True


def test_should_exempt_fixme_with_trailing_prose() -> None:
    token = _build_comment_token("# FIXME(jdoe): retry budget feels wrong")
    assert _is_exempt_python_comment(token) is True


def test_should_exempt_shebang_at_line_one_column_zero() -> None:
    token = tokenize.TokenInfo(
        type=tokenize.COMMENT,
        string="#!/usr/bin/env python3",
        start=(1, 0),
        end=(1, 22),
        line="#!/usr/bin/env python3\n",
    )
    assert _is_exempt_python_comment(token) is True


def test_should_flag_shebang_lookalike_off_line_one() -> None:
    token = tokenize.TokenInfo(
        type=tokenize.COMMENT,
        string="#!/usr/bin/env python3",
        start=(42, 0),
        end=(42, 22),
        line="#!/usr/bin/env python3\n",
    )
    assert _is_exempt_python_comment(token) is False


def test_check_comments_python_flags_chained_noqa_inline_comment() -> None:
    source = "x = 1  # noqa: F401  # this is just a description\n"
    issues = check_comments_python(source)
    assert issues, "chained noqa inline comment must be flagged"
    assert "Line 1" in issues[0]


def test_check_comments_python_does_not_flag_justified_type_ignore() -> None:
    source = "x = some_value()  # type: ignore[arg-type]  # third-party stub gap\n"
    issues = check_comments_python(source)
    assert issues == []
