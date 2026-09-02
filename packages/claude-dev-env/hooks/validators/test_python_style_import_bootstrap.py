"""Tests for the sys.path bootstrap-guard idiom recognizer."""

import ast

from .python_style_import_bootstrap import (
    is_docstring_statement,
    is_import_statement,
    is_sys_path_bootstrap_prelude,
    resolve_seen_non_import,
)


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


class TestIsImportStatement:
    """Tests pinning which statements the import-order scan treats as imports."""

    def test_import_statement_is_recognized(self) -> None:
        """A plain `import` statement is recognized."""
        assert is_import_statement(_module_body("import os\n")[0]) is True

    def test_from_import_statement_is_recognized(self) -> None:
        """A `from ... import ...` statement is recognized."""
        assert is_import_statement(_module_body("from os import path\n")[0]) is True

    def test_assignment_is_not_an_import_statement(self) -> None:
        """An assignment is not treated as an import."""
        assert is_import_statement(_module_body("X = 1\n")[0]) is False


class TestIsDocstringStatement:
    """Tests pinning which statements the import-order scan treats as docstrings."""

    def test_leading_string_literal_is_a_docstring(self) -> None:
        """A bare string-literal expression statement is a docstring."""
        assert is_docstring_statement(_module_body('"""A module docstring."""\n')[0]) is True

    def test_assignment_is_not_a_docstring(self) -> None:
        """An assignment is not a docstring, even with a string value."""
        assert is_docstring_statement(_module_body('X = "not a docstring"\n')[0]) is False


class TestResolveSeenNonImport:
    """Tests pinning when a pending statement run flips the "seen non-import" flag."""

    def test_already_flagged_stays_flagged(self) -> None:
        """Once flagged, the flag never resets, even with an empty pending run."""
        assert resolve_seen_non_import(True, []) is True

    def test_no_pending_statements_stays_unflagged(self) -> None:
        """An import with no statements before it since the last import stays unflagged."""
        assert resolve_seen_non_import(False, []) is False

    def test_bootstrap_prelude_does_not_flag(self) -> None:
        """A pending run that forms the bootstrap idiom does not flip the flag."""
        pending = _module_body(
            "_hooks_dir = str(Path(__file__).resolve().parent)\n"
            "if _hooks_dir not in sys.path:\n"
            "    sys.path.insert(0, _hooks_dir)\n"
        )
        assert resolve_seen_non_import(
            has_seen_non_import=False, all_pending_prelude_statements=pending
        ) is False

    def test_ordinary_code_flags(self) -> None:
        """A pending run with no bootstrap guard flips the flag."""
        pending = _module_body("MY_CONSTANT = 42\n")
        assert resolve_seen_non_import(False, pending) is True
