"""Tests for the sys.path bootstrap-guard idiom in the import-order check.

Split from ``test_python_style_checks.py`` to stay under its line cap,
matching the existing ``test_python_style_checks_decorator_gap.py`` split.
"""

import ast
from pathlib import Path

from .python_style_checks import check_imports_at_top

SYS_PATH_BOOTSTRAP_GUARD_IMPORTS = """import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.something import NAME  # noqa: E402
"""

TWO_SYS_PATH_BOOTSTRAP_GUARD_BLOCKS = """import sys
from pathlib import Path

_first_dir = str(Path(__file__).resolve().parent)
if _first_dir not in sys.path:
    sys.path.insert(0, _first_dir)

from hooks_constants.first import FIRST_NAME  # noqa: E402

_second_dir = str(Path(__file__).resolve().parent.parent)
if _second_dir not in sys.path:
    sys.path.insert(0, _second_dir)

from hooks_constants.second import SECOND_NAME  # noqa: E402
"""

UNGUARDED_SYS_PATH_INSERT_THEN_IMPORT = """import sys

sys.path.insert(0, "/some/hooks/dir")

import os
"""


class TestSysPathBootstrapGuardImportOrder:
    """Tests pinning the sys.path bootstrap-guard exemption in import ordering."""

    def test_sys_path_bootstrap_guard_passes(self) -> None:
        """The mandated dedup-guard idiom must not flag its own import."""
        tree = ast.parse(SYS_PATH_BOOTSTRAP_GUARD_IMPORTS)
        violations = check_imports_at_top(tree, "test.py")
        assert violations == []

    def test_two_sys_path_bootstrap_guard_blocks_pass(self) -> None:
        """Two separate bootstrap-guard blocks in one file both pass."""
        tree = ast.parse(TWO_SYS_PATH_BOOTSTRAP_GUARD_BLOCKS)
        violations = check_imports_at_top(tree, "test.py")
        assert violations == []

    def test_unguarded_sys_path_insert_still_fails(self) -> None:
        """A bare sys.path.insert with no membership guard still counts as ordinary code.

        Only the guarded idiom `check_sys_path_insert_deduplication_guard`
        mandates is exempt. An unguarded insert is itself a violation of that
        same guard, so an import after it stays flagged rather than rewarding
        the shape the other gate penalizes.
        """
        tree = ast.parse(UNGUARDED_SYS_PATH_INSERT_THEN_IMPORT)
        violations = check_imports_at_top(tree, "test.py")
        assert len(violations) == 1
        assert violations[0].line == 5

    def test_code_rules_enforcer_bootstrap_produces_no_findings(self) -> None:
        """The enforcer's own real bootstrap block goes from 29 findings to 0."""
        enforcer_path = (
            Path(__file__).resolve().parent.parent / "blocking" / "code_rules_enforcer.py"
        )
        tree = ast.parse(enforcer_path.read_text(encoding="utf-8"))
        violations = check_imports_at_top(tree, str(enforcer_path))
        assert violations == []
