"""Unit tests for TYPE_CHECKING-scoped import exemption in code-rules-enforcer."""

import importlib.util
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIR / "code-rules-enforcer.py",
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
