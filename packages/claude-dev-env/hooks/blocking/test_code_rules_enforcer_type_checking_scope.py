"""Unit tests for TYPE_CHECKING-scoped import exemption in code_rules_enforcer."""

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
check_imports_at_top = hook_module.check_imports_at_top


def test_should_allow_import_inside_if_type_checking_block() -> None:
    content = (
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from foo import Bar\n"
    )
    issues = check_imports_at_top(content)
    assert issues == []


def test_should_flag_runtime_import_inside_function_even_if_file_uses_type_checking() -> (
    None
):
    content = (
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from foo import Bar\n"
        "\n"
        "def baz():\n"
        "    import os\n"
        "    return os\n"
    )
    issues = check_imports_at_top(content)
    assert len(issues) == 1
    assert issues[0].startswith("Line 7:")
    assert "Import inside function" in issues[0]


def test_should_still_allow_top_level_imports() -> None:
    content = (
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "def do_something():\n"
        "    return os.getcwd()\n"
    )
    issues = check_imports_at_top(content)
    assert issues == []


def test_should_flag_import_inside_function_in_file_without_type_checking() -> None:
    content = "import os\n\ndef do_something():\n    import sys\n    return sys\n"
    issues = check_imports_at_top(content)
    assert len(issues) == 1
    assert "Import inside function" in issues[0]


def test_should_allow_typing_dot_type_checking_block() -> None:
    content = "import typing\n\nif typing.TYPE_CHECKING:\n    from foo import Bar\n"
    issues = check_imports_at_top(content)
    assert issues == []


def test_should_flag_function_import_after_type_checking_block_ends() -> None:
    content = (
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from foo import Bar\n"
        "\n"
        "def helper():\n"
        "    from json import loads\n"
        "    return loads\n"
    )
    issues = check_imports_at_top(content)
    assert len(issues) == 1
    assert "Import inside function" in issues[0]


def test_should_track_only_innermost_type_checking_block() -> None:
    """Pin documented single-level tracking: after a nested inner block ends,
    subsequent function-body imports at the outer block's indent are flagged
    as if outside any TYPE_CHECKING scope. See check_imports_at_top docstring.
    """
    content = (
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    def helper():\n"
        "        if TYPE_CHECKING:\n"
        "            from a import A\n"
        "        from b import B\n"
        "        return B\n"
    )
    issues = check_imports_at_top(content)
    assert len(issues) == 1
    assert issues[0].startswith("Line 7:")
    assert "Import inside function" in issues[0]


def test_should_skip_docstring_lines_starting_with_import_keyword() -> None:
    """Docstring sentences that incidentally start with ``from `` or ``import `` after
    stripping must not trigger the import-inside-function check.
    """
    content = (
        "def helper():\n"
        '    """Apply the priority queue atomically.\n'
        "\n"
        "    from a rename within the trailing-revenue window the duplicate\n"
        "    import the loaders for the cycle so the writer can advance.\n"
        '    """\n'
        "    return 42\n"
    )
    issues = check_imports_at_top(content)
    assert issues == []


def test_should_still_flag_real_import_after_docstring_closes() -> None:
    """An actual import statement after a one-line docstring closes must still flag."""
    content = (
        "def helper():\n"
        '    """One-line docstring."""\n'
        "    import os\n"
        "    return os\n"
    )
    issues = check_imports_at_top(content)
    assert len(issues) == 1
    assert "Import inside function" in issues[0]


def test_should_skip_triple_single_quoted_docstring_lines() -> None:
    """Triple-single-quote (''') docstrings exempt their interior lines too."""
    content = (
        "def helper():\n"
        "    '''Apply the cycle reset.\n"
        "\n"
        "    from a rename within the cycle window the writer would advance.\n"
        "    '''\n"
        "    return 1\n"
    )
    issues = check_imports_at_top(content)
    assert issues == []


def test_should_flag_real_import_after_multi_line_docstring_closes() -> None:
    """Real imports landing AFTER a multi-line docstring closes must still flag,
    confirming the triple-quote state correctly transitions back to ``None``.
    """
    content = (
        "def helper():\n"
        '    """Apply the priority queue atomically.\n'
        "\n"
        "    from a rename within the cycle window.\n"
        '    """\n'
        "    import os\n"
        "    return os\n"
    )
    issues = check_imports_at_top(content)
    assert len(issues) == 1
    assert "Import inside function" in issues[0]


def test_should_skip_module_level_docstring_text() -> None:
    """A module-level docstring containing ``from ``/``import `` text must not flag.

    The check ignores top-level lines regardless of triple-quote state because
    function-tracking is the only path that produces issues, but this exercises
    the entry-condition path where the docstring opens on line 1.
    """
    content = (
        '"""Module docstring opener.\n'
        "\n"
        "from a rename within the trailing-revenue window.\n"
        '"""\n'
        "\n"
        "def helper():\n"
        "    return 1\n"
    )
    issues = check_imports_at_top(content)
    assert issues == []


def test_should_flag_module_level_import_after_top_level_def() -> None:
    """A module-scope import placed below a top-level function must flag.

    This is the "imports mid-file after test functions" drift: the imports sit
    at indent zero (module scope), so the inside-function tracker never sees
    them, yet they violate the imports-at-top rule.
    """
    content = (
        "import os\n"
        "\n"
        "def first_test():\n"
        "    return os.getcwd()\n"
        "\n"
        "from pathlib import Path\n"
        "\n"
        "def second_test():\n"
        "    return Path('.')\n"
    )
    issues = check_imports_at_top(content)
    assert len(issues) == 1
    assert issues[0].startswith("Line 6:")
    assert "after top-level definition" in issues[0]


def test_should_flag_module_level_import_after_top_level_class() -> None:
    content = (
        "class Widget:\n"
        "    pass\n"
        "\n"
        "from collections import OrderedDict\n"
    )
    issues = check_imports_at_top(content)
    assert len(issues) == 1
    assert issues[0].startswith("Line 4:")
    assert "after top-level definition" in issues[0]


def test_should_allow_type_checking_import_after_top_level_def() -> None:
    content = (
        "from typing import TYPE_CHECKING\n"
        "\n"
        "def helper():\n"
        "    return 1\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from foo import Bar\n"
    )
    issues = check_imports_at_top(content)
    assert issues == []


def test_should_allow_indented_import_in_main_guard_after_def() -> None:
    content = (
        "def helper():\n"
        "    return 1\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    import argparse\n"
        "    helper()\n"
    )
    issues = check_imports_at_top(content)
    assert issues == []


def test_should_not_flag_top_level_imports_before_any_definition() -> None:
    content = (
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "def helper():\n"
        "    return Path(os.getcwd())\n"
    )
    issues = check_imports_at_top(content)
    assert issues == []
