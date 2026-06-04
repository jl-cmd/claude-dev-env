"""Behavior tests for the code_rules_test_isolation code-rules check module."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_test_isolation import (  # noqa: E402
    _build_alias_canonicalization_map,
    _collect_os_environ_local_binding_names,
    _collect_pathlib_path_local_binding_names,
    check_tests_use_isolated_filesystem_paths,
)

code_rules_enforcer = SimpleNamespace(
    _build_alias_canonicalization_map=_build_alias_canonicalization_map,
    _collect_os_environ_local_binding_names=_collect_os_environ_local_binding_names,
    _collect_pathlib_path_local_binding_names=_collect_pathlib_path_local_binding_names,
    check_tests_use_isolated_filesystem_paths=check_tests_use_isolated_filesystem_paths,
)


def _function_node_named(source: str, function_name: str) -> ast.FunctionDef:
    syntax_tree = ast.parse(source)
    for each_node in syntax_tree.body:
        if isinstance(each_node, ast.FunctionDef) and each_node.name == function_name:
            return each_node
    raise AssertionError(f"no function named {function_name!r} in source")


def test_isolation_check_ignores_path_constructor_expanduser_with_tilde_free_argument() -> None:
    """`Path('/tmp/x').expanduser()` carries no leading tilde, so it expands no
    home directory and must stay symmetric with `os.path.expanduser` of a
    tilde-free literal — neither fires."""
    source = (
        "from pathlib import Path\n"
        "def test_resolves_absolute() -> None:\n"
        "    target = Path('/tmp/x').expanduser()\n"
        "    target.read_text()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == []


def test_isolation_check_ignores_static_pathlib_expanduser_with_dynamic_argument() -> None:
    """`pathlib.Path.expanduser(some_path)` with a non-constant argument cannot
    be inspected for a leading tilde, so it follows the conservative rule and
    does not fire — symmetric with `os.path.expanduser(some_path)`."""
    source = (
        "import pathlib\n"
        "def test_resolves_dynamic(some_path) -> None:\n"
        "    target = pathlib.Path.expanduser(some_path)\n"
        "    target.read_text()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == []


def test_isolation_check_flags_path_home_via_function_local_class_alias() -> None:
    """`path_class = Path` then `path_class.home()` reaches the real home
    directory through a per-test class alias and must fire just like the bare
    `Path.home()` form."""
    source = (
        "from pathlib import Path\n"
        "def test_reads_home() -> None:\n"
        "    path_class = Path\n"
        "    home_dir = path_class.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("home" in each_issue.lower() for each_issue in issues)


def test_isolation_check_flags_getenv_via_function_local_callable_alias() -> None:
    """`read_env = os.getenv` then `read_env('HOME')` reads HOME through a
    per-test callable alias and must fire just like the bare `os.getenv('HOME')`
    form."""
    source = (
        "import os\n"
        "def test_reads_home() -> None:\n"
        "    read_env = os.getenv\n"
        "    home = read_env('HOME')\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("HOME" in each_issue for each_issue in issues)


def test_isolation_check_flags_tempfile_spooled_temporary_file() -> None:
    """`tempfile.SpooledTemporaryFile()` allocates in the shared temp dir and
    must fire as a temp-isolation probe alongside the other tempfile factories."""
    source = (
        "import tempfile\n"
        "def test_writes_spooled_temp() -> None:\n"
        "    handle = tempfile.SpooledTemporaryFile()\n"
        "    handle.write(b'x')\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("SpooledTemporaryFile" in each_issue for each_issue in issues)


def test_isolation_check_flags_tempfile_gettempdirb() -> None:
    """`tempfile.gettempdirb()` returns the shared temp dir as bytes and must
    fire just like the string-returning `tempfile.gettempdir()`."""
    source = (
        "import tempfile\n"
        "def test_resolves_temp_bytes() -> None:\n"
        "    base = tempfile.gettempdirb()\n"
        "    print(base)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("gettempdirb" in each_issue for each_issue in issues)


def test_isolation_check_flags_module_level_from_os_import_environ_subscript() -> None:
    """A module-level `from os import environ` binds `environ` to `os.environ`,
    so `environ['HOME']` inside a test must fire even without a per-test
    local binding."""
    source = (
        "from os import environ\n"
        "def test_resolves_home() -> None:\n"
        "    home = environ['HOME']\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("HOME" in each_issue for each_issue in issues)


def test_isolation_check_reports_probes_in_source_order_on_new_file() -> None:
    """On a new file (``all_changed_lines is None``) every probe is in scope and
    reported in source order — none dropped by the cap, which now trims only
    out-of-scope advisory noise."""
    probe_count = 20
    repeated_probes = "\n".join(
        f"    p{each_index} = Path.home()" for each_index in range(probe_count)
    )
    source = (
        f"from pathlib import Path\ndef test_many_probes() -> None:\n{repeated_probes}\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    first_probe_line_number = 3
    reported_line_numbers = [
        int(each_issue.split(":", maxsplit=1)[0].removeprefix("Line ").strip())
        for each_issue in issues
    ]
    expected_line_numbers = [
        first_probe_line_number + each_offset for each_offset in range(probe_count)
    ]
    assert reported_line_numbers == expected_line_numbers


def test_collect_pathlib_path_bindings_only_sees_the_scope_node_function() -> None:
    """The Path-binding collector must scope its walk to the function node it
    is given. A `p = Path('~/x')` binding in test_a must not appear when the
    collector is handed test_b's node (test_b never binds `p` to a Path)."""
    source = (
        "from pathlib import Path\n"
        "def test_a() -> None:\n"
        "    p = Path('~/x')\n"
        "    p.expanduser()\n"
        "def test_b(p) -> None:\n"
        "    p.expanduser()\n"
    )
    syntax_tree = ast.parse(source)
    alias_map = code_rules_enforcer._build_alias_canonicalization_map(syntax_tree)
    test_a_node = _function_node_named(source, "test_a")
    test_b_node = _function_node_named(source, "test_b")

    test_a_bindings = code_rules_enforcer._collect_pathlib_path_local_binding_names(
        test_a_node, alias_map
    )
    test_b_bindings = code_rules_enforcer._collect_pathlib_path_local_binding_names(
        test_b_node, alias_map
    )

    assert "p" in test_a_bindings
    assert "p" not in test_b_bindings


def test_collect_os_environ_bindings_only_sees_the_scope_node_function() -> None:
    """The environ-binding collector must scope its walk to the function node
    it is given. An `e = os.environ` binding in test_a must not appear when the
    collector is handed test_b's node (test_b never binds `e`)."""
    source = (
        "import os\n"
        "def test_a() -> None:\n"
        "    e = os.environ\n"
        "    home = e['HOME']\n"
        "    print(home)\n"
        "def test_b(e) -> None:\n"
        "    home = e['HOME']\n"
        "    print(home)\n"
    )
    syntax_tree = ast.parse(source)
    alias_map = code_rules_enforcer._build_alias_canonicalization_map(syntax_tree)
    test_a_node = _function_node_named(source, "test_a")
    test_b_node = _function_node_named(source, "test_b")

    test_a_bindings = code_rules_enforcer._collect_os_environ_local_binding_names(
        test_a_node, alias_map
    )
    test_b_bindings = code_rules_enforcer._collect_os_environ_local_binding_names(
        test_b_node, alias_map
    )

    assert "e" in test_a_bindings
    assert "e" not in test_b_bindings


def test_function_local_from_os_import_environ_does_not_leak_into_sibling_test() -> None:
    """bugbot-1: a function-local `from os import environ` in test_a binds
    `environ` only for test_a's runtime. A sibling test_b that references the
    bare name `environ` without importing it must not be flagged, while the
    test that actually imports and probes HOME (test_a) must be flagged."""
    source = (
        "def test_a() -> None:\n"
        "    from os import environ\n"
        "    home = environ['HOME']\n"
        "    print(home)\n"
        "def test_b() -> None:\n"
        "    home = environ['HOME']\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("test_a" in each_issue for each_issue in issues), (
        f"test_a's own function-local environ import must be flagged, got: {issues!r}"
    )
    assert not any("test_b" in each_issue for each_issue in issues), (
        "test_b references bare `environ` it never imports, so the function-local "
        f"import in test_a must not leak into it, got: {issues!r}"
    )


def test_function_local_aliased_module_import_does_not_leak_into_sibling_test() -> None:
    """bugbot-1 sibling: a function-local `import os as o` in test_a aliases
    `o` only for test_a. test_b referencing `o.getenv('HOME')` without its own
    import must not be flagged; test_a's own probe must be flagged."""
    source = (
        "def test_a() -> None:\n"
        "    import os as o\n"
        "    home = o.getenv('HOME')\n"
        "    print(home)\n"
        "def test_b() -> None:\n"
        "    home = o.getenv('HOME')\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("test_a" in each_issue for each_issue in issues), (
        f"test_a's own function-local aliased import must be flagged, got: {issues!r}"
    )
    assert not any("test_b" in each_issue for each_issue in issues), (
        "test_b references alias `o` it never bound, so the function-local "
        f"import in test_a must not leak into it, got: {issues!r}"
    )
