"""Tests for check_docstring_length_constant_superlative_vs_exact_gate.

A config module defines an integer ``*_LENGTH`` constant and its docstring
describes it with a superlative word ("the longest color string the swatch
accepts"), while the only consumer treats the constant as an exact-length
equality gate ("len(hex_color) != COLOR_AARRGGBB_LENGTH") in a sibling module.
A shorter valid string is rejected, not accepted at a shorter length, so the
"longest" prose claims a range of accepted lengths the code never allows. This
is the deterministic exact-gate slice of Category O6/O8
docstring-vs-implementation drift.

The package trees these tests build live under a neutral OS temp directory
rather than the pytest ``tmp_path`` fixture: the production check exempts any
path containing "test", and the pytest fixture root carries that substring, so a
fixture-rooted package would be skipped as test code and prove nothing.
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


def check_length_gate(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_length_constant_superlative_vs_exact_gate(
        content, file_path
    )


SUPERLATIVE_SWATCH_MODULE = '''"""Color-swatch rendering constants for the HTML run report.

These constants name the longest color string the swatch accepts and the
channel maximum the alpha byte is divided by.
"""

from typing import Final

COLOR_AARRGGBB_LENGTH: Final[int] = 9
'''


def _run_gate_over_package(
    swatch_content: str, consumer_body: str, swatch_basename: str = "color_swatch.py"
) -> list[str]:
    with tempfile.TemporaryDirectory() as temp_root:
        config_directory = Path(temp_root) / "stp_contrast_fix" / "config"
        config_directory.mkdir(parents=True)
        swatch_path = config_directory / swatch_basename
        swatch_path.write_text(swatch_content, encoding="utf-8")
        consumer_path = config_directory.parent / "html_report_fragments.py"
        consumer_path.write_text(consumer_body, encoding="utf-8")
        return check_length_gate(swatch_content, str(swatch_path))


def test_superlative_describing_exact_length_gate_is_flagged() -> None:
    consumer_body = (
        "from config.color_swatch import COLOR_AARRGGBB_LENGTH\n\n\n"
        "def to_css(hex_color: str) -> str | None:\n"
        '    if not hex_color.startswith("#") or len(hex_color) != '
        "COLOR_AARRGGBB_LENGTH:\n"
        "        return None\n"
        "    return hex_color\n"
    )
    issues = _run_gate_over_package(SUPERLATIVE_SWATCH_MODULE, consumer_body)
    assert len(issues) == 1
    assert "COLOR_AARRGGBB_LENGTH" in issues[0]


def test_ordered_comparison_treated_as_maximum_is_not_flagged() -> None:
    consumer_body = (
        "from config.color_swatch import COLOR_AARRGGBB_LENGTH\n\n\n"
        "def truncated(hex_color: str) -> bool:\n"
        "    return len(hex_color) <= COLOR_AARRGGBB_LENGTH\n"
    )
    assert _run_gate_over_package(SUPERLATIVE_SWATCH_MODULE, consumer_body) == []


def test_no_superlative_phrase_is_not_flagged() -> None:
    plain_module = (
        '"""The exact required #AARRGGBB length the swatch renders."""\n\n'
        "from typing import Final\n\n"
        "COLOR_AARRGGBB_LENGTH: Final[int] = 9\n"
    )
    consumer_body = (
        "from config.color_swatch import COLOR_AARRGGBB_LENGTH\n\n\n"
        "def to_css(hex_color: str) -> bool:\n"
        "    return len(hex_color) == COLOR_AARRGGBB_LENGTH\n"
    )
    assert _run_gate_over_package(plain_module, consumer_body) == []


def test_constant_without_length_suffix_is_not_flagged() -> None:
    non_length_module = (
        '"""The longest swatch threshold value used by the renderer."""\n\n'
        "from typing import Final\n\n"
        "COLOR_CHANNEL_MAXIMUM: Final[int] = 255\n"
    )
    consumer_body = (
        "from config.color_swatch import COLOR_CHANNEL_MAXIMUM\n\n\n"
        "def saturated(channel: str) -> bool:\n"
        "    return len(channel) == COLOR_CHANNEL_MAXIMUM\n"
    )
    assert _run_gate_over_package(non_length_module, consumer_body) == []


def test_constant_with_no_length_comparison_is_not_flagged() -> None:
    consumer_body = (
        "from config.color_swatch import COLOR_AARRGGBB_LENGTH\n\n\n"
        "def pad(hex_color: str) -> str:\n"
        "    return hex_color.ljust(COLOR_AARRGGBB_LENGTH)\n"
    )
    assert _run_gate_over_package(SUPERLATIVE_SWATCH_MODULE, consumer_body) == []


def test_syntax_error_returns_empty() -> None:
    issues = check_length_gate(
        "def broken(\n", "/stp_contrast_fix/config/color_swatch.py"
    )
    assert issues == []
