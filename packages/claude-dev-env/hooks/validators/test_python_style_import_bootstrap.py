"""Tests for the sys.path bootstrap-guard idiom recognizer."""

import ast

from .python_style_import_bootstrap import is_sys_path_bootstrap_prelude


def _module_body(source: str) -> list[ast.stmt]:
    """Return the top-level statements of *source* for use as a pending run."""
    return ast.parse(source).body


class TestIsSysPathBootstrapPrelude:
    """Tests pinning which statement runs qualify as the bootstrap prelude."""

    def test_empty_run_is_not_a_prelude(self) -> None:
        """An empty run carries no guard, so it is not the bootstrap idiom."""
        assert is_sys_path_bootstrap_prelude([]) is False

    def test_guard_alone_is_a_prelude(self) -> None:
        """A bare guarded insert, with no preceding assignment, still counts."""
        body = _module_body(
            'if "/some/dir" not in sys.path:\n    sys.path.insert(0, "/some/dir")\n'
        )
        assert is_sys_path_bootstrap_prelude(body) is True

    def test_assignment_feeding_guard_is_a_prelude(self) -> None:
        """The mandated `path = ...` plus guarded insert pair passes."""
        body = _module_body(
            "_hooks_dir = str(Path(__file__).resolve().parent)\n"
            "if _hooks_dir not in sys.path:\n"
            "    sys.path.insert(0, _hooks_dir)\n"
        )
        assert is_sys_path_bootstrap_prelude(body) is True

    def test_unrelated_trailing_constant_stays_a_prelude(self) -> None:
        """A plain constant sitting alongside a real guard does not break it.

        Mirrors code_rules_enforcer.py's own bootstrap block, which tucks an
        unrelated `_codex_apply_patch_tool_name = "apply_patch"` constant
        right after its guarded sys.path.insert calls.
        """
        body = _module_body(
            "_hooks_dir = str(Path(__file__).resolve().parent)\n"
            "if _hooks_dir not in sys.path:\n"
            "    sys.path.insert(0, _hooks_dir)\n"
            '_codex_apply_patch_tool_name = "apply_patch"\n'
        )
        assert is_sys_path_bootstrap_prelude(body) is True

    def test_plain_assignments_with_no_guard_are_not_a_prelude(self) -> None:
        """Assignments alone, with no guard anywhere, are ordinary code."""
        body = _module_body("MY_CONSTANT = 42\n")
        assert is_sys_path_bootstrap_prelude(body) is False

    def test_unguarded_insert_is_not_a_prelude(self) -> None:
        """A bare sys.path.insert with no membership guard is ordinary code."""
        body = _module_body('sys.path.insert(0, "/some/dir")\n')
        assert is_sys_path_bootstrap_prelude(body) is False

    def test_guard_alongside_a_function_def_is_not_a_prelude(self) -> None:
        """A real statement (a function def) in the run still counts as ordinary code."""
        body = _module_body(
            'if "/some/dir" not in sys.path:\n'
            '    sys.path.insert(0, "/some/dir")\n'
            "def foo() -> None:\n"
            "    pass\n"
        )
        assert is_sys_path_bootstrap_prelude(body) is False
