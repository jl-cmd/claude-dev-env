from __future__ import annotations

import importlib.util
from pathlib import Path

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location("code_rules_enforcer", ENFORCER_PATH)
assert specification is not None and specification.loader is not None
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_PATH = "C:/project/pkg/menu_info_colors.py"


def _check(source: str) -> list[str]:
    return code_rules_enforcer.check_whitespace_indentation_magic(source, PRODUCTION_PATH)


def test_flags_twelve_space_indent_constant() -> None:
    source = 'def fallback_indent() -> str:\n    return "            "\n'
    issues = _check(source)
    assert len(issues) == 1
    assert "Line 2" in issues[0]


def test_flags_indent_fragment_inside_fstring() -> None:
    source = 'def build(value: str) -> str:\n    return value + f"\\n            {value}"\n'
    issues = _check(source)
    assert len(issues) == 1
    assert "Line 2" in issues[0]


def test_flags_tab_indent_constant() -> None:
    source = 'def tabbed() -> str:\n    return "\\t\\t"\n'
    assert len(_check(source)) == 1


def test_does_not_flag_single_tab_delimiter() -> None:
    source = 'def split_columns(text: str) -> list[str]:\n    return text.split("\\t")\n'
    assert _check(source) == []


def test_does_not_flag_single_tab_join_delimiter() -> None:
    source = 'def join_rows(rows: list[str]) -> str:\n    return "\\t".join(rows)\n'
    assert _check(source) == []


def test_does_not_flag_single_space() -> None:
    source = 'def join_words(left: str, right: str) -> str:\n    return left + " " + right\n'
    assert _check(source) == []


def test_does_not_flag_newline_only_fragment() -> None:
    source = 'def build(value: str) -> str:\n    return f"\\n{value}"\n'
    assert _check(source) == []


def test_does_not_flag_docstring_with_spaced_words() -> None:
    source = (
        "def documented() -> str:\n"
        '    """A docstring with    spaced    words."""\n'
        '    return documented.__doc__ or ""\n'
    )
    assert _check(source) == []


def test_does_not_flag_in_config_file() -> None:
    source = 'def fallback_indent() -> str:\n    return "            "\n'
    assert (
        code_rules_enforcer.check_whitespace_indentation_magic(
            source, "C:/project/pkg/config/indents.py"
        )
        == []
    )
