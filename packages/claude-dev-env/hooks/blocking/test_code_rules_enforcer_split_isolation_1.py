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


def test_isolation_check_does_not_flag_expanduser_without_tilde_argument() -> None:
    """expanduser of a tilde-free string does not probe HOME and must not fire."""
    source = (
        "import os\n"
        "def test_resolves_relative() -> None:\n"
        "    target = os.path.expanduser('relative/path')\n"
        "    assert target\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == [], f"tilde-free expanduser must not be flagged, got: {issues!r}"


def test_isolation_check_flags_expanduser_with_tilde_argument() -> None:
    """expanduser of a leading-tilde string resolves HOME and must fire."""
    source = (
        "import os\n"
        "def test_reads_home() -> None:\n"
        "    target = os.path.expanduser('~/.config/x')\n"
        "    assert target\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("expanduser" in each_issue for each_issue in issues)


def test_isolation_check_flags_path_constructor_expanduser_method() -> None:
    """`Path('~/x').expanduser()` expands the home directory through the bound
    Path object and must fire even though it bypasses the static probe chain."""
    source = (
        "from pathlib import Path\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = Path('~/x').expanduser()\n"
        "    target.read_text()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("expanduser" in each_issue for each_issue in issues)


def test_isolation_check_flags_aliased_path_constructor_expanduser_method() -> None:
    """`from pathlib import Path as P` then `P('~/x').expanduser()` resolves the
    constructor through alias canonicalization and must fire."""
    source = (
        "from pathlib import Path as P\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = P('~/x').expanduser()\n"
        "    target.read_text()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("expanduser" in each_issue for each_issue in issues)


def test_isolation_check_flags_tempfile_named_temporary_file() -> None:
    """`tempfile.NamedTemporaryFile()` allocates in the shared temp dir and must
    fire as a temp-isolation probe."""
    source = (
        "import tempfile\n"
        "def test_writes_named_temp() -> None:\n"
        "    handle = tempfile.NamedTemporaryFile()\n"
        "    handle.write(b'x')\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("NamedTemporaryFile" in each_issue for each_issue in issues)


def test_isolation_check_exempts_tempfile_factory_with_explicit_dir() -> None:
    """A tempfile factory given an explicit `dir=` argument allocates under the
    supplied sandbox, so it must not fire as a shared-temp isolation probe."""
    source = (
        "import tempfile\n"
        "def test_writes_named_temp(tmp_path) -> None:\n"
        "    handle = tempfile.NamedTemporaryFile(dir=tmp_path)\n"
        "    handle.write(b'x')\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == []


def test_isolation_check_flags_tempfile_factory_with_dir_constant_none() -> None:
    """`dir=None` selects the default shared temp directory, so the factory
    still allocates from shared temp and must fire."""
    source = (
        "import tempfile\n"
        "def test_writes_named_temp() -> None:\n"
        "    handle = tempfile.NamedTemporaryFile(dir=None)\n"
        "    handle.write(b'x')\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("NamedTemporaryFile" in each_issue for each_issue in issues)


def test_isolation_check_flags_tempfile_factory_with_dir_getenv_tmpdir() -> None:
    """`dir=os.getenv('TMPDIR')` resolves to a shared-temp env source, so the
    factory still allocates from shared temp and must fire."""
    source = (
        "import os\n"
        "import tempfile\n"
        "def test_makes_temp_dir() -> None:\n"
        "    holder = tempfile.mkdtemp(dir=os.getenv('TMPDIR'))\n"
        "    print(holder)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("mkdtemp" in each_issue for each_issue in issues)


def test_isolation_check_exempts_tempfile_factory_with_dir_tmp_path() -> None:
    """`dir=tmp_path` allocates under the pytest sandbox, so the factory is
    isolated and must not fire."""
    source = (
        "import tempfile\n"
        "def test_makes_temp_dir(tmp_path) -> None:\n"
        "    holder = tempfile.mkdtemp(dir=tmp_path)\n"
        "    print(holder)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == []


def test_isolation_check_flags_class_level_probe_in_nested_class_body() -> None:
    """A Path.home() initializer in a nested class body runs at class-creation
    time during the test, so it must fire."""
    source = (
        "from pathlib import Path\n"
        "def test_defines_inner_class() -> None:\n"
        "    class Inner:\n"
        "        root = Path.home()\n"
        "    assert Inner is not None\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("Path.home" in each_issue for each_issue in issues)


def test_isolation_check_flags_from_os_import_path_expanduser() -> None:
    """`from os import path` binds `path` to `os.path`, so `path.expanduser`
    must resolve to the canonical `os.path.expanduser` probe and fire."""
    source = (
        "from os import path\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = path.expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("expanduser" in each_issue for each_issue in issues)


def test_isolation_check_flags_expandvars_with_windows_percent_userprofile() -> None:
    """expandvars expands Windows `%USERPROFILE%` percent syntax, so a percent
    reference to a home env var must fire."""
    source = (
        "import os\n"
        "def test_expands_userprofile() -> None:\n"
        "    target = os.path.expandvars('%USERPROFILE%\\\\.cfg')\n"
        "    open(target).read()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("expandvars" in each_issue for each_issue in issues)


def test_isolation_check_ignores_expandvars_with_unrelated_windows_percent_var() -> None:
    """A percent reference to an unrelated env var does not probe HOME/TMP and
    must not fire."""
    source = (
        "import os\n"
        "def test_expands_unrelated() -> None:\n"
        "    token = os.path.expandvars('%MY_APP_TOKEN%')\n"
        "    print(token)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == []


def test_isolation_check_flags_environ_get_via_local_binding() -> None:
    """`e = os.environ` then `e.get('HOME')` reads HOME through a local alias
    and must fire just like the subscript `e['HOME']` form."""
    source = (
        "import os\n"
        "def test_resolves_home() -> None:\n"
        "    e = os.environ\n"
        "    home = e.get('HOME')\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("HOME" in each_issue for each_issue in issues)


def test_isolation_check_scopes_path_bindings_to_their_own_test() -> None:
    """A `p = Path('~/x')` binding in one test must not make an unrelated
    `p.expanduser()` in a sibling test a finding; bindings are per-test."""
    source = (
        "from pathlib import Path\n"
        "def test_a() -> None:\n"
        "    p = Path('~/x')\n"
        "    p.expanduser()\n"
        "def test_b(p) -> None:\n"
        "    p.expanduser()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("test_a" in each_issue for each_issue in issues)
    assert not any("test_b" in each_issue for each_issue in issues)


def test_isolation_check_scopes_environ_bindings_to_their_own_test() -> None:
    """An `e = os.environ` binding in one test must not make an unrelated
    `e['HOME']` in a sibling test a finding; bindings are per-test."""
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
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("test_a" in each_issue for each_issue in issues)
    assert not any("test_b" in each_issue for each_issue in issues)
