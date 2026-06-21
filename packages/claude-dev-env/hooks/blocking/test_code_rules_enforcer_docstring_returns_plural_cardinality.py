"""Tests for check_docstring_returns_plural_cardinality — O6 plural-stop drift.

A function returns a dict literal whose keys carry prefix families, and its
Returns clause names one such family with a plural noun ("the sheen stops")
while only one key in that family exists ("sheen_mid"). The plural prose claims
two or more entries the dict no longer holds. This is the deterministic
single-key slice of Category O6 docstring-prose-vs-implementation drift, the
shape that appears when a producer removes the second key in a family but leaves
the plural prose untouched.
"""

from __future__ import annotations

import importlib.util
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


def check_docstring_returns_plural_cardinality(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_returns_plural_cardinality(content, file_path)


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/phone_handset.py"
TEST_FILE_PATH = "/project/src/test_phone_handset.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _drifted_single_sheen_function() -> str:
    return (
        "def _palette_substitutions(colors: PhoneHandsetColors) -> dict[str, str]:\n"
        '    """Derive every SVG color field from the three theme hero colors.\n'
        "\n"
        "    Returns:\n"
        "        The color substitution fields the SVG template fills: the body form\n"
        "        stops (highlight, mid, shadow, inner-shadow), the sheen stops, the rim\n"
        "        highlight, the depth, and the specular core that lights the gloss.\n"
        '    """\n'
        "    return {\n"
        '        "body_highlight": derive_highlight(colors.body),\n'
        '        "body_mid": colors.body,\n'
        '        "body_shadow": derive_shadow(colors.body),\n'
        '        "body_inner_shadow": derive_inner(colors.body),\n'
        '        "sheen_mid": colors.sheen,\n'
        '        "rim_highlight": derive_rim(colors.sheen),\n'
        '        "specular_core": derive_specular(colors.sheen),\n'
        '        "depth_mid": colors.depth,\n'
        "    }\n"
    )


def _singular_sheen_function() -> str:
    return (
        "def _palette_substitutions(colors: PhoneHandsetColors) -> dict[str, str]:\n"
        '    """Derive every SVG color field from the three theme hero colors.\n'
        "\n"
        "    Returns:\n"
        "        The color substitution fields the SVG template fills: the body form\n"
        "        stops (highlight, mid, shadow, inner-shadow), the sheen stop, the rim\n"
        "        highlight, the depth, and the specular core that lights the gloss.\n"
        '    """\n'
        "    return {\n"
        '        "body_highlight": derive_highlight(colors.body),\n'
        '        "body_mid": colors.body,\n'
        '        "body_shadow": derive_shadow(colors.body),\n'
        '        "body_inner_shadow": derive_inner(colors.body),\n'
        '        "sheen_mid": colors.sheen,\n'
        '        "rim_highlight": derive_rim(colors.sheen),\n'
        '        "specular_core": derive_specular(colors.sheen),\n'
        '        "depth_mid": colors.depth,\n'
        "    }\n"
    )


def _plural_family_with_two_keys_function() -> str:
    return (
        "def _palette_substitutions(colors: PhoneHandsetColors) -> dict[str, str]:\n"
        '    """Derive every SVG color field from the three theme hero colors.\n'
        "\n"
        "    Returns:\n"
        "        The color substitution fields the SVG template fills: the body form\n"
        "        stops (highlight, mid, shadow, inner-shadow), the sheen stops, the rim\n"
        "        highlight, the depth, and the specular core that lights the gloss.\n"
        '    """\n'
        "    return {\n"
        '        "body_highlight": derive_highlight(colors.body),\n'
        '        "body_mid": colors.body,\n'
        '        "sheen_highlight": derive_sheen_highlight(colors.sheen),\n'
        '        "sheen_mid": colors.sheen,\n'
        '        "rim_highlight": derive_rim(colors.sheen),\n'
        '        "specular_core": derive_specular(colors.sheen),\n'
        "    }\n"
    )


def test_should_flag_plural_stops_with_single_family_key() -> None:
    issues = check_docstring_returns_plural_cardinality(
        _drifted_single_sheen_function(), PRODUCTION_FILE_PATH
    )
    assert any("sheen" in each for each in issues), (
        f"The plural 'sheen stops' against a single sheen_mid key must be flagged, got: {issues!r}"
    )


def test_should_report_category_o6_in_the_message() -> None:
    issues = check_docstring_returns_plural_cardinality(
        _drifted_single_sheen_function(), PRODUCTION_FILE_PATH
    )
    assert any("O6" in each for each in issues), (
        f"Expected the Category O6 label in the message, got: {issues!r}"
    )


def test_should_not_flag_singular_noun() -> None:
    issues = check_docstring_returns_plural_cardinality(
        _singular_sheen_function(), PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"A singular 'sheen stop' matching one key must not be flagged, got: {issues!r}"
    )


def test_should_not_flag_plural_family_with_two_keys() -> None:
    issues = check_docstring_returns_plural_cardinality(
        _plural_family_with_two_keys_function(), PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"A plural 'sheen stops' matching two sheen_ keys must not be flagged, got: {issues!r}"
    )


def test_should_not_flag_family_absent_from_dict() -> None:
    source = (
        "def build() -> dict[str, str]:\n"
        '    """Build the fields.\n'
        "\n"
        "    Returns:\n"
        "        The body stops and the sheen stops the template fills.\n"
        '    """\n'
        "    return {\n"
        '        "body_mid": "a",\n'
        '        "rim_highlight": "b",\n'
        "    }\n"
    )
    issues = check_docstring_returns_plural_cardinality(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A plural family with no matching dict keys must not be flagged, got: {issues!r}"
    )


def test_should_not_flag_when_no_returns_section() -> None:
    source = (
        "def build() -> dict[str, str]:\n"
        '    """Build the sheen stops without a Returns section."""\n'
        "    return {\n"
        '        "sheen_mid": "a",\n'
        "    }\n"
    )
    issues = check_docstring_returns_plural_cardinality(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A plural noun outside a Returns section must not be flagged, got: {issues!r}"
    )


def test_should_skip_test_file() -> None:
    issues = check_docstring_returns_plural_cardinality(
        _drifted_single_sheen_function(), TEST_FILE_PATH
    )
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_docstring_returns_plural_cardinality(
        _drifted_single_sheen_function(), HOOK_INFRASTRUCTURE_PATH
    )
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_docstring_returns_plural_cardinality("def fetch(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_validate_content_surfaces_plural_cardinality_drift() -> None:
    issues = validate_content(
        _drifted_single_sheen_function(), PRODUCTION_FILE_PATH, old_content=""
    )
    matching_issues = [each for each in issues if "sheen" in each and "O6" in each]
    assert matching_issues, (
        f"Expected validate_content to surface the O6 plural-cardinality drift, got: {issues!r}"
    )
