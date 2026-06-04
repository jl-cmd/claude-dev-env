"""Behavior tests for the code_rules_test_isolation code-rules check module."""

from __future__ import annotations

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
    check_tests_use_isolated_filesystem_paths,
)

code_rules_enforcer = SimpleNamespace(
    check_tests_use_isolated_filesystem_paths=check_tests_use_isolated_filesystem_paths,
)


def test_pathlib_binding_inside_nested_helper_does_not_leak_to_outer_test() -> None:
    """loop7-P2 (2690 sibling): a home-tilde ``Path('~')`` binding inside a
    standalone nested helper runs in its own scope; a same-named outer
    ``.expanduser()`` call must not be attributed to that binding."""
    source = (
        "from pathlib import Path\n"
        "def test_outer() -> None:\n"
        "    def nested_helper() -> None:\n"
        "        candidate = Path('~/config')\n"
        "        assert candidate\n"
        "    candidate = make_unrelated_path()\n"
        "    discovered = candidate.expanduser()\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_pathlib_nested_scope.py"
    )
    assert not any(
        "test_outer" in each_issue for each_issue in issues
    ), f"nested-helper pathlib binding must not leak to the outer test, got: {issues!r}"


def test_isolation_check_exempts_usefixtures_monkeypatch_decorator() -> None:
    """A test isolated via ``@pytest.mark.usefixtures("monkeypatch")`` injects the
    monkeypatch fixture without a signature parameter and must be exempt from the
    HOME/TMP probe, mirroring the signature-parameter suppression."""
    source = (
        "import os\n"
        "import pytest\n"
        "@pytest.mark.usefixtures('monkeypatch')\n"
        "def test_reads_home() -> None:\n"
        "    home = os.environ['HOME']\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == [], (
        "a test decorated with usefixtures('monkeypatch') is isolated and must "
        f"not be flagged; got: {issues!r}"
    )


def test_isolation_check_still_flags_usefixtures_without_monkeypatch() -> None:
    """``@pytest.mark.usefixtures("tmp_path")`` does not inject monkeypatch, so a
    HOME probe in its body must still be flagged."""
    source = (
        "import os\n"
        "import pytest\n"
        "@pytest.mark.usefixtures('tmp_path')\n"
        "def test_reads_home() -> None:\n"
        "    home = os.environ['HOME']\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("HOME" in each_issue for each_issue in issues), (
        "usefixtures('tmp_path') does not intercept env reads, so the HOME probe "
        f"must still be flagged; got: {issues!r}"
    )
