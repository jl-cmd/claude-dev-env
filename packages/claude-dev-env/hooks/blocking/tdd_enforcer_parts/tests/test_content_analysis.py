"""Behavioral tests for the content_analysis parts module."""

from tdd_enforcer_parts import content_analysis


def test_constants_only_accepts_module_docstring_and_assignment() -> None:
    content = '"""doc."""\nMAX_ORDERS = 3\n'
    assert content_analysis._is_constants_only_python_content(content) is True


def test_constants_only_rejects_function_definition() -> None:
    assert content_analysis._is_constants_only_python_content("def f():\n    return 1\n") is False


def test_constants_only_accepts_join_on_a_string_literal_inside_re_compile() -> None:
    content = (
        '"""doc."""\n'
        "import re\n"
        "NAMES = ('one', 'two')\n"
        'PATTERN = re.compile("(" + "|".join(NAMES) + ")")\n'
    )
    assert content_analysis._is_constants_only_python_content(content) is True


def test_constants_only_rejects_join_on_a_non_literal_receiver() -> None:
    content = (
        '"""doc."""\n'
        'SEPARATOR = "|"\n'
        'NAMES = ("one", "two")\n'
        "PATTERN = SEPARATOR.join(NAMES)\n"
    )
    assert content_analysis._is_constants_only_python_content(content) is False


def test_constants_only_rejects_a_non_allowlisted_method_on_a_string_literal() -> None:
    content = '"""doc."""\nSHOUT = "hi".upper()\n'
    assert content_analysis._is_constants_only_python_content(content) is False


def test_post_edit_import_only_allows_import_removal() -> None:
    existing = "import os\n\ndef run(): return 1\n"
    tool_input = {"old_string": "import os\n", "new_string": ""}
    assert content_analysis._is_post_edit_import_only(existing, "Edit", tool_input) is True


def test_post_edit_import_only_blocks_import_swap() -> None:
    existing = "import os\n\ndef run(): return 1\n"
    tool_input = {"old_string": "import os", "new_string": "import sys"}
    assert content_analysis._is_post_edit_import_only(existing, "Edit", tool_input) is False


def test_post_edit_constants_only_allows_constant_value_change() -> None:
    existing = '"""doc."""\nMAX_ORDERS = 3\n'
    tool_input = {"old_string": "MAX_ORDERS = 3", "new_string": "MAX_ORDERS = 5"}
    assert content_analysis._is_post_edit_constants_only(existing, "Edit", tool_input) is True
