"""Unit tests for the inline-tuple snake_case-string-magic check in code_rules_enforcer.

These tests cover the gap surfaced during PR #419: a tuple literal whose first
element is a snake_case string (e.g. ``("kept", "Unknown status")``) inside a
function body slipped past the Write/Edit hook even though the commit-time
gate caught it.
"""

import importlib.util
import pathlib
import sys

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
check_inline_tuple_string_magic = hook_module.check_inline_tuple_string_magic
validate_content = hook_module.validate_content

PRODUCTION_FILE_PATH = "packages/app/services/loader.py"
TEST_FILE_PATH = "packages/app/services/test_loader.py"
CONFIG_FILE_PATH = "packages/app/config/labels.py"


def test_should_flag_inline_snake_case_tuple_pair_inside_function() -> None:
    content = "def describe(glyph):\n    return {'a': ('kept', 'Unknown status')}\n"
    issues = check_inline_tuple_string_magic(content, PRODUCTION_FILE_PATH)
    assert any("'kept'" in each_issue for each_issue in issues), (
        f"Expected 'kept' tuple-pair flagged, got: {issues}"
    )


def test_should_flag_inline_snake_case_tuple_inside_dict_value() -> None:
    content = "def lookup():\n    return {'STATUS_KEPT': ('kept', 'Patch unchanged')}\n"
    issues = check_inline_tuple_string_magic(content, PRODUCTION_FILE_PATH)
    assert any("'kept'" in each_issue for each_issue in issues), (
        f"Expected nested tuple flagged, got: {issues}"
    )


def test_should_flag_first_element_snake_case_with_underscore() -> None:
    content = "def label():\n    return ('unknown_status', 'placeholder')\n"
    issues = check_inline_tuple_string_magic(content, PRODUCTION_FILE_PATH)
    assert any("'unknown_status'" in each_issue for each_issue in issues), (
        f"Expected snake_case-with-underscore flagged, got: {issues}"
    )


def test_should_not_flag_tuple_outside_function_body() -> None:
    content = "ALL_STATUS = ('kept', 'Unknown status')\n"
    issues = check_inline_tuple_string_magic(content, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Module-level constants are not in function bodies; must not flag, got: {issues}"
    )


def test_should_skip_test_files() -> None:
    content = "def test_thing():\n    return ('kept', 'Unknown status')\n"
    issues = check_inline_tuple_string_magic(content, TEST_FILE_PATH)
    assert issues == [], f"Test files are exempt, got: {issues}"


def test_should_skip_config_files() -> None:
    content = "def build():\n    return ('kept', 'Unknown status')\n"
    issues = check_inline_tuple_string_magic(content, CONFIG_FILE_PATH)
    assert issues == [], f"Config files are exempt, got: {issues}"


def test_should_not_flag_tuple_with_non_snake_case_first_element() -> None:
    content = "def render():\n    return ('Title Case', 'Body')\n"
    issues = check_inline_tuple_string_magic(content, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Non-snake-case strings are not column/key-like; must not flag, got: {issues}"
    )


def test_should_not_flag_short_string_first_element() -> None:
    content = "def render():\n    return ('ok', 'fine')\n"
    issues = check_inline_tuple_string_magic(content, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Strings shorter than minimum length are exempt, got: {issues}"
    )


def test_should_not_flag_keyword_strings() -> None:
    content = "def render():\n    return ('true', 'false')\n"
    issues = check_inline_tuple_string_magic(content, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Keyword literals (true/false/none/null) are exempt, got: {issues}"
    )


def test_should_not_flag_tuple_longer_than_pair() -> None:
    content = "def render():\n    return ('kept', 'Unknown status', 'extra')\n"
    issues = check_inline_tuple_string_magic(content, PRODUCTION_FILE_PATH)
    assert issues == [], f"Only two-element tuples are inspected, got: {issues}"


def test_should_dedupe_nested_function_tuples() -> None:
    """Tuples inside nested FunctionDefs must produce one finding, not many.

    Without deduplication the outer ast.walk enumerates every FunctionDef
    including nested ones, then the inner walk visits each tuple via every
    enclosing function. Must surface exactly one finding per tuple site.
    """
    content = (
        "def outer():\n"
        "    def inner():\n"
        '        x = ("some_column_name", 42)\n'
        "        return x\n"
        "    return inner\n"
    )
    issues = check_inline_tuple_string_magic(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1, f"expected 1 finding, got {len(issues)}: {issues!r}"


def test_validate_content_wires_check_for_python_files() -> None:
    content = "def describe(glyph):\n    return {'a': ('kept', 'Unknown status')}\n"
    issues = validate_content(content, PRODUCTION_FILE_PATH)
    assert any("'kept'" in each_issue for each_issue in issues), (
        f"validate_content must run the new check, got: {issues}"
    )
