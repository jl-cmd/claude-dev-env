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
    check_tests_use_isolated_filesystem_paths,
)

code_rules_enforcer = SimpleNamespace(
    _build_alias_canonicalization_map=_build_alias_canonicalization_map,
    check_tests_use_isolated_filesystem_paths=check_tests_use_isolated_filesystem_paths,
)


def test_build_alias_map_excludes_function_local_imports() -> None:
    """bugbot-1: the module-wide alias canonicalization map must be built only
    from top-level imports. A function-local `import os as o` and a
    function-local `from os import environ` must not appear in the shared map."""
    source = (
        "import tempfile as module_temp\n"
        "def test_a() -> None:\n"
        "    import os as o\n"
        "    from os import environ\n"
        "    print(o, environ)\n"
    )
    syntax_tree = ast.parse(source)
    alias_map = code_rules_enforcer._build_alias_canonicalization_map(syntax_tree)
    assert alias_map.get("module_temp") == "tempfile", (
        f"top-level alias must be recorded, got: {alias_map!r}"
    )
    assert "o" not in alias_map, (
        f"function-local `import os as o` must not leak into the module map, got: {alias_map!r}"
    )
    assert "environ" not in alias_map, (
        f"function-local `from os import environ` must not leak into the module map, got: {alias_map!r}"
    )


def test_module_level_from_os_import_environ_still_flags_every_referencing_test() -> None:
    """bugbot-1 guard: a genuine module-level `from os import environ` binds the
    name for the whole module, so every test that probes HOME through it must
    still be flagged. The per-function scoping must not suppress this case."""
    source = (
        "from os import environ\n"
        "def test_a() -> None:\n"
        "    print(environ['HOME'])\n"
        "def test_b() -> None:\n"
        "    print(environ['HOME'])\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("test_a" in each_issue for each_issue in issues)
    assert any("test_b" in each_issue for each_issue in issues), (
        f"module-level import must flag every probing test, got: {issues!r}"
    )


def test_build_alias_map_excludes_class_body_imports() -> None:
    """A probe alias imported inside a class body binds only inside that class
    scope, so it must not enter the module-wide alias canonicalization map. A
    genuine module-level alias in the same source must still be recorded."""
    source = (
        "import tempfile as module_temp\n"
        "class TestAlpha:\n"
        "    import tempfile as t\n"
        "    def test_alpha_probe(self) -> None:\n"
        "        assert self.t is not None\n"
    )
    syntax_tree = ast.parse(source)
    alias_map = code_rules_enforcer._build_alias_canonicalization_map(syntax_tree)
    assert alias_map.get("module_temp") == "tempfile", (
        f"top-level alias must be recorded, got: {alias_map!r}"
    )
    assert "t" not in alias_map, (
        f"class-body `import tempfile as t` must not leak into the module map, got: {alias_map!r}"
    )


def test_class_body_aliased_import_does_not_leak_into_sibling_test() -> None:
    """A class-body `import tempfile as t` aliases `t` only inside that class.
    A sibling top-level test taking `t` as a parameter and calling `t.mkdtemp()`
    must not be flagged, since the class-scoped alias never enters the
    module-wide map."""
    source = (
        "class TestAlpha:\n"
        "    import tempfile as t\n"
        "    def test_alpha_probe(self) -> None:\n"
        "        assert self.t is not None\n"
        "def test_sibling(t) -> None:\n"
        "    t.mkdtemp()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert not any("test_sibling" in each_issue for each_issue in issues), (
        "class-body alias must not leak into a sibling test through the "
        f"module-wide map, got: {issues!r}"
    )


def test_build_alias_map_records_module_top_level_but_excludes_function_and_class_imports() -> None:
    """Only true module-top-level imports enter the alias map. Imports lexically
    inside a function body or a class body are excluded, while a module-level
    try-guarded optional import is still recorded module-wide."""
    source = (
        "try:\n"
        "    import tempfile as guarded_temp\n"
        "except ImportError:\n"
        "    guarded_temp = None\n"
        "def test_function_local() -> None:\n"
        "    import tempfile as function_temp\n"
        "    assert function_temp is not None\n"
        "class TestBeta:\n"
        "    import tempfile as class_temp\n"
        "    def test_beta_probe(self) -> None:\n"
        "        assert self.class_temp is not None\n"
    )
    syntax_tree = ast.parse(source)
    alias_map = code_rules_enforcer._build_alias_canonicalization_map(syntax_tree)
    assert alias_map.get("guarded_temp") == "tempfile", (
        f"module-level try-guarded alias must be recorded, got: {alias_map!r}"
    )
    assert "function_temp" not in alias_map, (
        f"function-local alias must not enter the module map, got: {alias_map!r}"
    )
    assert "class_temp" not in alias_map, (
        f"class-body alias must not enter the module map, got: {alias_map!r}"
    )


def test_isolation_message_carries_enclosing_function_definition_span() -> None:
    """The isolation message must carry the enclosing test's definition line
    and line span so the commit gate can scope by the same function span the
    enforcer uses, while keeping the ``Line N:`` probe-line prefix intact."""
    header = "from pathlib import Path\n"
    test_body = (
        "def test_reads_home() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    source = header + test_body
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    definition_line = 2
    function_span = 3
    expected_span_fragment = (
        f"(defined at line {definition_line}, spanning {function_span} lines)"
    )
    assert any(
        each_issue.startswith("Line ") and expected_span_fragment in each_issue
        for each_issue in issues
    ), f"isolation message must carry the def-line + span fragment, got: {issues!r}"


def test_module_import_inside_top_level_try_is_retained_in_alias_map() -> None:
    """loop7-P2 (2566): a module-level ``try: import os as o`` is genuinely
    module-scoped; its alias must enter the shared canonicalization map so a
    later ``o.path.expanduser('~')`` inside a test is flagged."""
    source = (
        "try:\n"
        "    import os as o\n"
        "except ImportError:\n"
        "    o = None\n"
        "def test_reads_home() -> None:\n"
        "    discovered = o.path.expanduser('~')\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_optional_import.py"
    )
    assert any(
        "test_reads_home" in each_issue for each_issue in issues
    ), f"module import nested in top-level try must be retained, got: {issues!r}"


def test_direct_module_aliased_import_is_retained_in_alias_map() -> None:
    """loop7-P2 (2566): a plain top-level ``import os as o`` must still resolve so
    ``o.path.expanduser('~')`` inside a test is flagged."""
    source = (
        "import os as o\n"
        "def test_reads_home() -> None:\n"
        "    discovered = o.path.expanduser('~')\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_direct_import.py"
    )
    assert any(
        "test_reads_home" in each_issue for each_issue in issues
    ), f"direct module aliased import must resolve, got: {issues!r}"


def test_function_local_import_does_not_enter_shared_alias_map() -> None:
    """loop7-P2 (2566): an import inside one test must not canonicalize a
    same-named reference in a sibling test that never imported it."""
    source = (
        "def test_imports_locally() -> None:\n"
        "    import os as o\n"
        "    assert o\n"
        "def test_sibling_uses_o() -> None:\n"
        "    o = make_unrelated_object()\n"
        "    discovered = o.path.expanduser('~')\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_local_import_scope.py"
    )
    assert not any(
        "test_sibling_uses_o" in each_issue for each_issue in issues
    ), f"function-local import must not leak to a sibling test, got: {issues!r}"


def test_import_inside_nested_helper_does_not_leak_to_outer_test_overlay() -> None:
    """loop7-P2 (2690): an import inside a standalone nested helper runs in its own
    callable scope; its alias must not enter the outer test's overlay and flag a
    sibling reference in the outer body."""
    source = (
        "def test_outer() -> None:\n"
        "    def nested_helper() -> None:\n"
        "        import os as o\n"
        "        assert o\n"
        "    o = make_unrelated_object()\n"
        "    discovered = o.path.expanduser('~')\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_nested_helper_scope.py"
    )
    assert not any(
        "test_outer" in each_issue for each_issue in issues
    ), f"nested-helper import must not leak to the outer test, got: {issues!r}"


def test_environ_binding_inside_nested_helper_does_not_leak_to_outer_test() -> None:
    """loop7-P2 (2690 sibling): an ``os.environ`` binding inside a standalone
    nested helper runs in its own scope; a same-named outer reference must not be
    attributed to that binding."""
    source = (
        "import os\n"
        "def test_outer() -> None:\n"
        "    def nested_helper() -> None:\n"
        "        captured = os.environ\n"
        "        assert captured\n"
        "    captured = make_unrelated_mapping()\n"
        "    discovered = captured['HOME']\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_environ_nested_scope.py"
    )
    assert not any(
        "test_outer" in each_issue for each_issue in issues
    ), f"nested-helper environ binding must not leak to the outer test, got: {issues!r}"
