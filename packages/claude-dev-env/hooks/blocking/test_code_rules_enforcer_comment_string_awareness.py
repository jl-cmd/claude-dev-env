"""Tests pinning string-aware ``#`` detection in the Python comment checks.

``#`` characters appear inside string literals in three common shapes:
hex color codes (``"#FFFFFF"``), URL fragments
(``"https://x#section"``), and f-string interpolation patterns. None of
those ``#`` characters belong to a comment token. ``check_comments_python``
and the Python branch of ``extract_comment_texts`` route their ``#``
detection through ``tokenize.generate_tokens`` so only true ``COMMENT``
tokens are considered. These tests pin both halves of that contract:
``#``-in-strings is exempt; real inline comments that land AFTER such
a string still flag.
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
    check_comment_changes,
    check_comments_python,
    extract_comment_texts,
)

code_rules_enforcer = SimpleNamespace(
    check_comment_changes=check_comment_changes,
    check_comments_python=check_comments_python,
    extract_comment_texts=extract_comment_texts,
)


def test_python_check_should_not_flag_hex_color_literal() -> None:
    content = 'palette_primary = "#FFFFFF"\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == []


def test_python_check_should_not_flag_url_fragment_in_string() -> None:
    content = 'docs_link = "https://example.com/guide#installation"\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == []


def test_python_check_should_not_flag_hash_inside_fstring_interpolation() -> None:
    content = 'rendered = f"prefix #{count} suffix"\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == []


def test_python_check_should_not_flag_hash_inside_triple_quoted_string() -> None:
    content = 'message = """use # for inline comments"""\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == []


def test_python_check_should_flag_real_inline_comment_after_string_with_hash() -> None:
    content = 'name = "user"  # this comment must still flag\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert len(issues) == 1
    assert "Comment found" in issues[0]


def test_python_check_should_flag_real_comment_after_hex_color_literal() -> None:
    content = 'palette_primary = "#FFFFFF"  # accidentally added comment\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert len(issues) == 1
    assert "Comment found" in issues[0]


def test_extract_should_not_classify_hex_color_as_inline_comment() -> None:
    content = 'palette_primary = "#FFFFFF"\n'
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert inline == set()
    assert standalone == set()


def test_extract_should_classify_real_inline_comment_after_string_with_hash() -> None:
    content = 'name = "user"  # real comment\n'
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert len(inline) == 1
    assert "# real comment" in next(iter(inline))
    assert standalone == set()


def test_extract_should_classify_standalone_comment_correctly() -> None:
    content = "# standalone comment\nx = 1\n"
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert "# standalone comment" in standalone
    assert inline == set()


def test_extract_should_distinguish_inline_from_standalone_in_same_file() -> None:
    content = '# standalone first\nx = "#FFFFFF"  # inline real comment\n# standalone second\n'
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert "# inline real comment" in next(iter(inline))
    assert "# standalone first" in standalone
    assert "# standalone second" in standalone


def test_check_comment_changes_skips_removal_when_new_python_un_parseable() -> None:
    old_content = 'x = 1  # existing comment\n'
    new_content = '"""unterminated multi-line string\n'
    issues = code_rules_enforcer.check_comment_changes(old_content, new_content, "foo.py")
    assert issues == []


def test_check_comment_changes_skips_removal_when_old_python_un_parseable() -> None:
    old_content = '"""unterminated multi-line string\n'
    new_content = 'x = 1  # newly added comment\n'
    issues = code_rules_enforcer.check_comment_changes(old_content, new_content, "foo.py")
    assert issues == []


def test_check_comment_changes_still_detects_removal_on_parseable_python() -> None:
    old_content = 'x = 1  # existing comment\n'
    new_content = 'x = 1\n'
    issues = code_rules_enforcer.check_comment_changes(old_content, new_content, "foo.py")
    assert any("Existing comment removed" in each_issue for each_issue in issues)


def test_python_check_should_exempt_directive_without_space_after_hash() -> None:
    for each_directive in ("#noqa", "#type: ignore", "#pylint: disable", "#pragma: no cover"):
        content = f"{each_directive}\n"
        issues = code_rules_enforcer.check_comments_python(content)
        assert issues == [], f"expected exempt for {each_directive!r}"


def test_python_check_should_exempt_directive_with_tab_after_hash() -> None:
    content = "#\tnoqa: F401\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == []


def test_python_check_should_still_flag_unrelated_no_space_comment() -> None:
    content = "#realcomment text\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert len(issues) == 1


def test_extract_should_exempt_directive_without_space_after_hash() -> None:
    content = "#noqa\nx = 1\n"
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert standalone == set()
    assert inline == set()


def test_python_check_should_exempt_bare_hash_comment() -> None:
    for each_content in ("#\n", "#  \n", "x = 1  #\n"):
        issues = code_rules_enforcer.check_comments_python(each_content)
        assert issues == [], f"expected exempt for bare hash in {each_content!r}"


def test_extract_should_not_classify_bare_hash_as_comment() -> None:
    content = "#\nx = 1  #\n"
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert standalone == set()
    assert inline == set()


def test_python_check_should_exempt_true_shebang_on_line_one() -> None:
    content = "#!/usr/bin/env python3\nx = 1\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == []


def test_python_check_should_flag_inline_shebang_lookalike() -> None:
    content = "x = 1  #! hidden comment\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert len(issues) == 1


def test_python_check_should_flag_shebang_on_later_standalone_line() -> None:
    content = "x = 1\n#! not a real shebang\n"
    issues = code_rules_enforcer.check_comments_python(content)
    assert len(issues) == 1


def test_extract_should_classify_inline_shebang_lookalike_as_inline_comment() -> None:
    content = "x = 1  #! hidden\n"
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert inline != set()
    assert standalone == set()
