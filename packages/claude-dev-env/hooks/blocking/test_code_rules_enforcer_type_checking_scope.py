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
