"""Tests for ``check_tests_use_isolated_filesystem_paths``.

Pattern class: tests that call ``Path.home()``, ``os.path.expanduser('~')``,
``os.getenv('HOME'|'USERPROFILE'|'TMPDIR'|…)``, ``os.environ['HOME'|…]``, or
``tempfile.gettempdir()`` without taking a ``monkeypatch`` fixture leak across
the suite. Only ``monkeypatch`` suppresses the finding, because
``monkeypatch.setenv(...)`` actually intercepts the env reads the probes
depend on. ``tmp_path``, ``tmp_path_factory``, ``tmpdir``, and
``tmpdir_factory`` allocate a sandbox path but do not intercept env reads, so
their presence alone does not suppress the finding (see
``test_should_flag_path_home_when_only_tmp_path_fixture_present``). Cited
SYNTHESIS evidence: ccc#476 F16, F19, F28; pa#136 F11.
"""

from __future__ import annotations

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
check_tests_use_isolated_filesystem_paths = hook_module.check_tests_use_isolated_filesystem_paths

TEST_FILE_PATH = "/project/src/test_module.py"
PRODUCTION_FILE_PATH = "/project/src/module.py"


def test_should_flag_path_home_in_test_without_fixture() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile() -> None:\n"
        "    home_dir = Path.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_changed_lines_scope_skips_untouched_probe() -> None:
    """loop5-3: with changed_lines naming only an unrelated test, an untouched
    HOME probe in another test must not be reported."""
    source = (
        "from pathlib import Path\n"
        "def test_reads_home() -> None:\n"
        "    home_dir = Path.home()\n"
        "    assert home_dir\n"
        "def test_addition() -> None:\n"
        "    assert 2 + 2 == 4\n"
    )
    addition_assert_line = 6
    issues = check_tests_use_isolated_filesystem_paths(
        source, TEST_FILE_PATH, all_changed_lines={addition_assert_line}
    )
    assert issues == [], f"untouched probe must not be in scope, got: {issues!r}"


def test_changed_lines_scope_keeps_touched_probe() -> None:
    """loop5-3: when a changed line is the probe's source line, the violation
    must remain reported."""
    source = (
        "from pathlib import Path\n"
        "def test_reads_home() -> None:\n"
        "    home_dir = Path.home()\n"
        "    assert home_dir\n"
    )
    probe_line = 3
    issues = check_tests_use_isolated_filesystem_paths(
        source, TEST_FILE_PATH, all_changed_lines={probe_line}
    )
    assert any("Path.home" in each_issue for each_issue in issues)


def test_reports_only_in_scope_probe_among_untouched_ones() -> None:
    """loop5-2: an in-scope probe appearing after several untouched out-of-scope
    probes is still reported, while the untouched ones stay out of scope."""
    leading_probe_count = 5
    leading_tests = "".join(
        f"def test_leading_{each_index}() -> None:\n"
        f"    leading_home = Path.home()\n"
        f"    assert leading_home\n"
        for each_index in range(leading_probe_count)
    )
    header = "from pathlib import Path\n"
    target_test = (
        "def test_target() -> None:\n"
        "    target_home = Path.home()\n"
        "    assert target_home\n"
    )
    source = header + leading_tests + target_test
    target_probe_line = len(source.splitlines()) - 1
    issues = check_tests_use_isolated_filesystem_paths(
        source, TEST_FILE_PATH, all_changed_lines={target_probe_line}
    )
    assert any("test_target" in each_issue for each_issue in issues)
    assert not any("test_leading_" in each_issue for each_issue in issues)


def test_should_flag_path_home_when_only_tmp_path_fixture_present() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile(tmp_path) -> None:\n"
        "    home_dir = Path.home()\n"
        "    (tmp_path / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_flag_path_home_when_only_positional_only_tmp_path_present() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile(tmp_path, /) -> None:\n"
        "    home_dir = Path.home()\n"
        "    (tmp_path / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_allow_path_home_in_test_with_positional_only_monkeypatch_fixture() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile(monkeypatch, /) -> None:\n"
        "    monkeypatch.setenv('HOME', '/tmp/fake')\n"
        "    home_dir = Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_ignore_path_home_inside_nested_helper_function() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile() -> None:\n"
        "    def _nested_helper() -> Path:\n"
        "        return Path.home()\n"
        "    assert callable(_nested_helper)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_ignore_path_home_inside_nested_lambda() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_makes_lambda() -> None:\n"
        "    lookup_home = lambda: Path.home()\n"
        "    assert callable(lookup_home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_path_home_inside_nested_class_body() -> None:
    # A class-level statement directly in a nested class body runs at
    # class-creation time during the test, so a Path.home() initializer there
    # executes on the test's runtime path and must be flagged.
    source = (
        "from pathlib import Path\n"
        "def test_defines_inner_class() -> None:\n"
        "    class Inner:\n"
        "        root = Path.home()\n"
        "    assert Inner is not None\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_ignore_path_home_inside_uncalled_nested_class_method() -> None:
    # An ordinary method of a nested class does not run merely because the
    # class is defined during the test; Python only executes a method when it
    # is called. A Path.home() in the body of an uncalled method is therefore
    # not on the test's runtime path and must not be flagged.
    source = (
        "from pathlib import Path\n"
        "def test_defines_inner_class() -> None:\n"
        "    class Inner:\n"
        "        def resolve_root(self) -> Path:\n"
        "            return Path.home()\n"
        "    assert Inner is not None\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == [], (
        "an uncalled nested-class method body does not execute during the test, "
        f"so its Path.home() must not be flagged; got: {issues!r}"
    )


def test_should_ignore_path_home_inside_nested_class_method_lambda() -> None:
    # A lambda defined inside a nested class method is two callable scopes
    # removed from the test path; neither the method nor the lambda runs from
    # the class definition alone.
    source = (
        "from pathlib import Path\n"
        "def test_defines_inner_class() -> None:\n"
        "    class Inner:\n"
        "        def build(self) -> object:\n"
        "            return lambda: Path.home()\n"
        "    assert Inner is not None\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == [], (
        "a lambda inside an uncalled nested-class method must not be flagged; "
        f"got: {issues!r}"
    )


def test_should_ignore_nested_test_named_function_pytest_does_not_collect() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_outer_caller(monkeypatch) -> None:\n"
        "    monkeypatch.setenv('HOME', '/tmp/fake')\n"
        "    def test_home_helper() -> None:\n"
        "        Path.home()\n"
        "    assert callable(test_home_helper)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_still_flag_path_home_at_top_level_when_nested_helper_also_probes() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_top_level_probe_survives_nested_scope() -> None:\n"
        "    target = Path.home() / '.myapp'\n"
        "    def _nested_helper() -> Path:\n"
        "        return Path.home()\n"
        "    target.write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)
    assert len(issues) == 1


def test_should_allow_path_home_in_test_with_monkeypatch_fixture() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile(monkeypatch, tmp_path) -> None:\n"
        "    monkeypatch.setenv('HOME', str(tmp_path))\n"
        "    home_dir = Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_expanduser_call_without_isolation() -> None:
    source = (
        "import os\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = os.path.expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_tempfile_gettempdir_without_isolation() -> None:
    source = (
        "import tempfile\n"
        "def test_writes_to_shared_temp() -> None:\n"
        "    base = tempfile.gettempdir()\n"
        "    (base + '/x.txt')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("gettempdir" in each_issue for each_issue in issues)


def test_should_flag_os_environ_subscript_for_home() -> None:
    source = (
        "import os\n"
        "def test_resolves_home() -> None:\n"
        "    home = os.environ['HOME']\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_flag_os_environ_subscript_for_userprofile() -> None:
    source = (
        "import os\n"
        "def test_resolves_userprofile() -> None:\n"
        "    user = os.environ['USERPROFILE']\n"
        "    print(user)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("USERPROFILE" in each_issue for each_issue in issues)


def test_should_flag_os_getenv_for_tmpdir() -> None:
    source = (
        "import os\n"
        "def test_resolves_tmpdir() -> None:\n"
        "    tmp_root = os.getenv('TMPDIR')\n"
        "    print(tmp_root)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("TMPDIR" in each_issue for each_issue in issues)


def test_should_not_flag_os_getenv_for_unrelated_var() -> None:
    source = (
        "import os\n"
        "def test_unrelated_env() -> None:\n"
        "    value = os.getenv('MY_APP_TOKEN')\n"
        "    print(value)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_expandvars_referencing_home_env_var() -> None:
    source = (
        "import os\n"
        "def test_expands_home() -> None:\n"
        "    target = os.path.expandvars('$HOME/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expandvars" in each_issue for each_issue in issues)


def test_should_flag_expandvars_referencing_temp_env_var() -> None:
    source = (
        "import os\n"
        "def test_expands_temp() -> None:\n"
        "    target = os.path.expandvars('$TEMP/scratch')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expandvars" in each_issue for each_issue in issues)


def test_should_flag_expandvars_with_braced_home_reference() -> None:
    source = (
        "import os\n"
        "def test_expands_braced_home() -> None:\n"
        "    target = os.path.expandvars('${USERPROFILE}/Documents')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expandvars" in each_issue for each_issue in issues)


def test_should_not_flag_expandvars_referencing_unrelated_var() -> None:
    source = (
        "import os\n"
        "def test_expands_unrelated() -> None:\n"
        "    token = os.path.expandvars('$MY_APP_TOKEN')\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_bare_imported_expanduser() -> None:
    source = (
        "from os.path import expanduser\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_bare_imported_expanduser_under_alias() -> None:
    source = (
        "from os.path import expanduser as expand_home\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = expand_home('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_aliased_os_path_module_expanduser() -> None:
    source = (
        "import os.path as op\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = op.expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_bare_imported_getenv_for_home() -> None:
    source = (
        "from os import getenv\n"
        "def test_resolves_home() -> None:\n"
        "    home = getenv('HOME')\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_not_flag_bare_imported_getenv_for_unrelated_var() -> None:
    source = (
        "from os import getenv\n"
        "def test_resolves_token() -> None:\n"
        "    token = getenv('MY_APP_TOKEN')\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_aliased_os_module_path_expanduser() -> None:
    source = (
        "import os as o\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = o.path.expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_aliased_os_module_getenv_for_home() -> None:
    source = (
        "import os as o\n"
        "def test_resolves_home() -> None:\n"
        "    home = o.getenv('HOME')\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_not_flag_aliased_os_module_getenv_for_unrelated_var() -> None:
    source = (
        "import os as o\n"
        "def test_resolves_token() -> None:\n"
        "    token = o.getenv('MY_APP_TOKEN')\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_os_environ_via_local_binding() -> None:
    source = (
        "import os\n"
        "def test_resolves_home() -> None:\n"
        "    e = os.environ\n"
        "    home = e['HOME']\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_not_flag_os_environ_local_binding_for_unrelated_var() -> None:
    source = (
        "import os\n"
        "def test_resolves_token() -> None:\n"
        "    e = os.environ\n"
        "    token = e['MY_APP_TOKEN']\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_os_environ_get_via_local_binding() -> None:
    source = (
        "import os\n"
        "def test_resolves_home() -> None:\n"
        "    e = os.environ\n"
        "    home = e.get('HOME')\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_not_flag_os_environ_get_local_binding_for_unrelated_var() -> None:
    source = (
        "import os\n"
        "def test_resolves_token() -> None:\n"
        "    e = os.environ\n"
        "    token = e.get('MY_APP_TOKEN')\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_canonical_os_environ_get_for_home() -> None:
    source = (
        "import os\n"
        "def test_resolves_home() -> None:\n"
        "    home = os.environ.get('HOME')\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_not_flag_path_binding_leaking_from_a_different_test() -> None:
    # The Path-binding collector must scope its bindings to the test currently
    # being analyzed. A `p = Path('~/x')` binding in test_a must NOT make an
    # unrelated `p.expanduser()` in test_b a finding (test_b never bound `p`
    # to a Path). Module-wide binding collection produces this false positive.
    source = (
        "from pathlib import Path\n"
        "def test_a() -> None:\n"
        "    p = Path('~/x')\n"
        "    p.expanduser()\n"
        "def test_b(p) -> None:\n"
        "    p.expanduser()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("test_a" in each_issue for each_issue in issues)
    assert not any("test_b" in each_issue for each_issue in issues)


def test_should_flag_path_binding_used_within_the_same_test() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_within_one_test() -> None:\n"
        "    p = Path('~/x')\n"
        "    p.expanduser()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)
    assert any("test_within_one_test" in each_issue for each_issue in issues)


def test_should_not_flag_environ_binding_leaking_from_a_different_test() -> None:
    # The environ-binding collector must scope its bindings to the test
    # currently being analyzed. An `e = os.environ` binding in test_a must NOT
    # make an unrelated `e['HOME']` in test_b a finding (test_b never bound
    # `e` to os.environ). Module-wide binding collection produces this false
    # positive.
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
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("test_a" in each_issue for each_issue in issues)
    assert not any("test_b" in each_issue for each_issue in issues)


def test_should_flag_environ_binding_used_within_the_same_test() -> None:
    source = (
        "import os\n"
        "def test_within_one_test() -> None:\n"
        "    e = os.environ\n"
        "    home = e['HOME']\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)
    assert any("test_within_one_test" in each_issue for each_issue in issues)


def test_should_flag_module_level_from_os_import_environ_subscript() -> None:
    source = (
        "from os import environ\n"
        "def test_resolves_home() -> None:\n"
        "    home = environ['HOME']\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)
    assert any("test_resolves_home" in each_issue for each_issue in issues)


def test_should_not_flag_module_level_from_os_import_environ_for_unrelated_var() -> None:
    source = (
        "from os import environ\n"
        "def test_resolves_token() -> None:\n"
        "    token = environ['MY_APP_TOKEN']\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_ignore_path_home_inside_nested_function_within_nested_class_method() -> None:
    # A function nested inside an uncalled nested-class method is two callable
    # scopes removed from the test path. Neither the method nor the inner
    # function runs from the class definition alone, so the probe must not be
    # flagged.
    source = (
        "from pathlib import Path\n"
        "class TestFoo:\n"
        "    def test_unsafe(self) -> None:\n"
        "        class HomePath:\n"
        "            def build(self) -> Path:\n"
        "                def _inner() -> Path:\n"
        "                    return Path.home()\n"
        "                return _inner()\n"
        "        h = HomePath()\n"
        "        assert h is not None\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == [], (
        "a probe inside an uncalled nested-class method body must stay out of "
        f"scope; got: {issues!r}"
    )


def test_should_ignore_lambda_probe_inside_nested_class_method() -> None:
    # A lambda body inside a nested-class method runs only when the method
    # runs, which the class definition alone does not trigger. The method body
    # is a callable-scope boundary, so the lambda probe must not be flagged.
    source = (
        "from pathlib import Path\n"
        "class TestFoo:\n"
        "    def test_unsafe(self) -> None:\n"
        "        class HomePath:\n"
        "            def build(self):\n"
        "                return (lambda: Path.home())()\n"
        "        h = HomePath()\n"
        "        assert h is not None\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == [], (
        "a lambda probe inside an uncalled nested-class method body must stay "
        f"out of scope; got: {issues!r}"
    )


def test_should_not_run_on_production_files() -> None:
    source = (
        "from pathlib import Path\ndef test_writes_dotfile() -> None:\n    home_dir = Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_ignore_module_level_helpers_in_test_files() -> None:
    source = (
        "from pathlib import Path\n"
        "def helper_paths() -> Path:\n"
        "    return Path.home()\n"
        "def test_uses_helper(tmp_path) -> None:\n"
        "    helper_paths()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_ignore_helper_named_with_bare_test_prefix() -> None:
    source = (
        "from pathlib import Path\n"
        "def testing_factory() -> Path:\n"
        "    return Path.home()\n"
        "def testify_connection() -> Path:\n"
        "    return Path.home()\n"
        "def testament_root() -> Path:\n"
        "    return Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_aliased_path_home_probe() -> None:
    source = (
        "from pathlib import Path as P\n"
        "def test_writes_dotfile() -> None:\n"
        "    home_dir = P.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("home" in each_issue.lower() for each_issue in issues)


def test_should_flag_aliased_module_import_home_probe() -> None:
    source = (
        "import pathlib as pathlib_alias\n"
        "def test_writes_dotfile() -> None:\n"
        "    home_dir = pathlib_alias.Path.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("home" in each_issue.lower() for each_issue in issues)


def test_should_allow_aliased_path_home_with_monkeypatch_fixture() -> None:
    source = (
        "from pathlib import Path as P\n"
        "def test_writes_dotfile(monkeypatch) -> None:\n"
        "    monkeypatch.setenv('HOME', '/tmp/fake')\n"
        "    home_dir = P.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_handle_async_test_functions() -> None:
    source = (
        "from pathlib import Path\n"
        "async def test_writes_dotfile() -> None:\n"
        "    home_dir = Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_recognize_should_prefix_functions_as_tests() -> None:
    source = (
        "from pathlib import Path\n"
        "def should_write_dotfile() -> None:\n"
        "    home_dir = Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_skip_when_source_fails_to_parse() -> None:
    source = "def test_broken(:\n"
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_edit_drops_every_out_of_scope_probe() -> None:
    """An edit that touches none of the probe lines reports nothing — every
    probe is out of scope (untouched code must not block a single-file edit), so
    the cap has nothing in scope to preserve."""
    repeated_probes = "\n".join(f"    p{each_index} = Path.home()" for each_index in range(20))
    source = f"from pathlib import Path\ndef test_many_probes() -> None:\n{repeated_probes}\n"
    untouched_line_far_outside_any_probe = 100000
    issues = check_tests_use_isolated_filesystem_paths(
        source,
        TEST_FILE_PATH,
        all_changed_lines={untouched_line_far_outside_any_probe},
    )
    assert issues == []


def test_new_file_reports_every_probe_uncapped() -> None:
    """On a new file (``all_changed_lines is None``) every line is in scope, so
    the cap must not drop a probe — all are reported."""
    probe_count = 20
    repeated_probes = "\n".join(
        f"    p{each_index} = Path.home()" for each_index in range(probe_count)
    )
    source = f"from pathlib import Path\ndef test_many_probes() -> None:\n{repeated_probes}\n"
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert len(issues) == probe_count


def test_should_ignore_test_method_inside_non_test_prefixed_helper_class() -> None:
    # Helper classes (non-Test* prefix) are not collected by pytest under the
    # repo's `python_classes = Test*` setting, so methods on them must not
    # produce HOME/TMP isolation findings.
    source = (
        "from pathlib import Path\n"
        "class HelperFactory:\n"
        "    def test_makes_home_probe(self) -> Path:\n"
        "        return Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_test_method_inside_test_prefixed_class() -> None:
    # Test*-prefixed classes ARE collected by pytest under the repo's
    # `python_classes = Test*` setting, so methods on them must still produce
    # HOME/TMP isolation findings.
    source = (
        "from pathlib import Path\n"
        "class TestHomeProbing:\n"
        "    def test_makes_home_probe(self) -> None:\n"
        "        home_dir = Path.home()\n"
        "        (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_ignore_path_home_inside_nested_class_method_of_outer_test() -> None:
    # A method of a nested class is a callable-scope boundary. Python does not
    # run a method just because its class is defined, and static analysis
    # cannot reliably tell which methods a later instantiation calls. The
    # walker treats every nested-class method body as a boundary, so a
    # Path.home() in __init__ is not attributed to the outer test.
    source = (
        "from pathlib import Path\n"
        "class TestFoo:\n"
        "    def test_unsafe(self) -> None:\n"
        "        class HomePath:\n"
        "            def __init__(self) -> None:\n"
        "                self.real_home = Path.home()\n"
        "        h = HomePath()\n"
        "        assert h is not None\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == [], (
        "a probe inside a nested-class method body must stay out of scope; "
        f"got: {issues!r}"
    )


def test_should_ignore_path_home_inside_standalone_nested_helper_function() -> None:
    # A standalone nested function defined inside a test body is its own
    # callable scope — it carries its own isolation contract and is not
    # part of the test's direct execution path. Probes there must remain
    # unattributed to the outer test (preserves existing scope boundary).
    source = (
        "from pathlib import Path\n"
        "def test_outer() -> None:\n"
        "    def helper() -> Path:\n"
        "        return Path.home()\n"
        "    assert callable(helper)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_expanduser_with_tilde_only_argument() -> None:
    source = (
        "import os\n"
        "def test_reads_home() -> None:\n"
        "    target = os.path.expanduser('~')\n"
        "    assert target\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_expanduser_with_named_user_tilde_argument() -> None:
    source = (
        "import os\n"
        "def test_reads_other_home() -> None:\n"
        "    target = os.path.expanduser('~alice/.config')\n"
        "    assert target\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_not_flag_expanduser_with_relative_path_without_tilde() -> None:
    source = (
        "import os\n"
        "def test_resolves_relative() -> None:\n"
        "    target = os.path.expanduser('relative/path')\n"
        "    assert target\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_not_flag_expanduser_with_non_constant_argument() -> None:
    source = (
        "import os\n"
        "def test_resolves_dynamic(some_path) -> None:\n"
        "    target = os.path.expanduser(some_path)\n"
        "    assert target\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_from_os_import_path_expanduser() -> None:
    source = (
        "from os import path\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = path.expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_from_os_import_path_expandvars_home_var() -> None:
    source = (
        "from os import path\n"
        "def test_expands_home() -> None:\n"
        "    target = path.expandvars('$HOME/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expandvars" in each_issue for each_issue in issues)


def test_should_flag_from_os_import_path_under_alias_expanduser() -> None:
    source = (
        "from os import path as p\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = p.expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_expandvars_with_windows_percent_userprofile() -> None:
    source = (
        "import os\n"
        "def test_expands_userprofile() -> None:\n"
        "    target = os.path.expandvars('%USERPROFILE%\\\\.cfg')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expandvars" in each_issue for each_issue in issues)


def test_should_flag_expandvars_with_windows_percent_temp() -> None:
    source = (
        "import os\n"
        "def test_expands_temp() -> None:\n"
        "    target = os.path.expandvars('%TEMP%\\\\scratch')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expandvars" in each_issue for each_issue in issues)


def test_should_not_flag_expandvars_with_windows_percent_unrelated_var() -> None:
    source = (
        "import os\n"
        "def test_expands_unrelated() -> None:\n"
        "    token = os.path.expandvars('%MY_APP_TOKEN%')\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_bare_imported_expandvars_home_var() -> None:
    source = (
        "from os.path import expandvars\n"
        "def test_expands_home() -> None:\n"
        "    target = expandvars('$HOME/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expandvars" in each_issue for each_issue in issues)


def test_should_flag_from_pathlib_import_path_without_alias() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_reads_home() -> None:\n"
        "    home_dir = Path.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_flag_path_constructor_expanduser_method_call() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = Path('~/x').expanduser()\n"
        "    target.read_text()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_aliased_path_constructor_expanduser_method_call() -> None:
    source = (
        "from pathlib import Path as P\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = P('~/x').expanduser()\n"
        "    target.read_text()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_pathlib_path_constructor_expanduser_method_call() -> None:
    source = (
        "import pathlib\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = pathlib.Path('~/x').expanduser()\n"
        "    target.read_text()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_expanduser_on_path_bound_local_variable() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_reads_dotfile() -> None:\n"
        "    candidate = Path('~/x')\n"
        "    target = candidate.expanduser()\n"
        "    target.read_text()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_static_pathlib_path_expanduser_with_tilde_argument() -> None:
    source = (
        "import pathlib\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = pathlib.Path.expanduser('~/x')\n"
        "    target.read_text()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_not_flag_static_pathlib_path_expanduser_with_dynamic_argument() -> None:
    source = (
        "import pathlib\n"
        "def test_resolves_dynamic(some_path) -> None:\n"
        "    target = pathlib.Path.expanduser(some_path)\n"
        "    target.read_text()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_not_flag_static_pathlib_path_expanduser_with_tilde_free_argument() -> None:
    source = (
        "import pathlib\n"
        "def test_resolves_relative() -> None:\n"
        "    target = pathlib.Path.expanduser('relative/path')\n"
        "    target.read_text()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_allow_path_constructor_expanduser_with_monkeypatch_fixture() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_reads_dotfile(monkeypatch) -> None:\n"
        "    monkeypatch.setenv('HOME', '/tmp/fake')\n"
        "    target = Path('~/x').expanduser()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_not_flag_expanduser_on_non_path_local_variable() -> None:
    source = (
        "def test_reads_dotfile(some_object) -> None:\n"
        "    target = some_object.expanduser()\n"
        "    print(target)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_tempfile_named_temporary_file_without_isolation() -> None:
    source = (
        "import tempfile\n"
        "def test_writes_named_temp() -> None:\n"
        "    handle = tempfile.NamedTemporaryFile()\n"
        "    handle.write(b'x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("NamedTemporaryFile" in each_issue for each_issue in issues)


def test_should_flag_tempfile_temporary_file_without_isolation() -> None:
    source = (
        "import tempfile\n"
        "def test_writes_temp() -> None:\n"
        "    handle = tempfile.TemporaryFile()\n"
        "    handle.write(b'x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("TemporaryFile" in each_issue for each_issue in issues)


def test_should_flag_tempfile_temporary_directory_without_isolation() -> None:
    source = (
        "import tempfile\n"
        "def test_makes_temp_dir() -> None:\n"
        "    holder = tempfile.TemporaryDirectory()\n"
        "    print(holder.name)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("TemporaryDirectory" in each_issue for each_issue in issues)


def test_should_flag_tempfile_mktemp_without_isolation() -> None:
    source = (
        "import tempfile\n"
        "def test_resolves_temp_name() -> None:\n"
        "    candidate = tempfile.mktemp()\n"
        "    print(candidate)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("mktemp" in each_issue for each_issue in issues)


def test_should_flag_bare_imported_tempfile_named_temporary_file() -> None:
    source = (
        "from tempfile import NamedTemporaryFile\n"
        "def test_writes_named_temp() -> None:\n"
        "    handle = NamedTemporaryFile()\n"
        "    handle.write(b'x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("NamedTemporaryFile" in each_issue for each_issue in issues)


def test_should_allow_tempfile_constructor_with_monkeypatch_fixture() -> None:
    source = (
        "import tempfile\n"
        "def test_writes_named_temp(monkeypatch) -> None:\n"
        "    monkeypatch.setenv('TMPDIR', '/tmp/fake')\n"
        "    handle = tempfile.NamedTemporaryFile()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_not_flag_path_constructor_expanduser_with_tilde_free_argument() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_resolves_absolute() -> None:\n"
        "    target = Path('/tmp/x').expanduser()\n"
        "    target.read_text()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_not_flag_path_constructor_expanduser_with_dynamic_argument() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_resolves_dynamic(some_path) -> None:\n"
        "    target = Path(some_path).expanduser()\n"
        "    target.read_text()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_not_flag_path_bound_local_expanduser_with_tilde_free_argument() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_resolves_absolute() -> None:\n"
        "    candidate = Path('/tmp/x')\n"
        "    target = candidate.expanduser()\n"
        "    target.read_text()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_path_home_via_function_local_class_alias() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_reads_home() -> None:\n"
        "    path_class = Path\n"
        "    home_dir = path_class.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("home" in each_issue.lower() for each_issue in issues)


def test_should_flag_getenv_via_function_local_callable_alias() -> None:
    source = (
        "import os\n"
        "def test_reads_home() -> None:\n"
        "    read_env = os.getenv\n"
        "    home = read_env('HOME')\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_not_flag_getenv_function_local_alias_for_unrelated_var() -> None:
    source = (
        "import os\n"
        "def test_reads_token() -> None:\n"
        "    read_env = os.getenv\n"
        "    token = read_env('MY_APP_TOKEN')\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_expanduser_via_function_local_os_path_module_alias() -> None:
    source = (
        "import os\n"
        "def test_reads_dotfile() -> None:\n"
        "    path_module = os.path\n"
        "    target = path_module.expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_mkdtemp_via_function_local_tempfile_module_alias() -> None:
    source = (
        "import tempfile\n"
        "def test_makes_temp_dir() -> None:\n"
        "    temp_module = tempfile\n"
        "    holder = temp_module.mkdtemp()\n"
        "    print(holder)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("mkdtemp" in each_issue for each_issue in issues)


def test_should_flag_path_home_via_function_local_pathlib_module_alias() -> None:
    source = (
        "import pathlib\n"
        "def test_reads_home() -> None:\n"
        "    pathlib_module = pathlib\n"
        "    home_dir = pathlib_module.Path.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("home" in each_issue.lower() for each_issue in issues)


def test_should_not_flag_local_class_alias_leaking_from_a_different_test() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_a() -> None:\n"
        "    path_class = Path\n"
        "    path_class.home()\n"
        "def test_b(path_class) -> None:\n"
        "    path_class.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("test_a" in each_issue for each_issue in issues)
    assert not any("test_b" in each_issue for each_issue in issues)


def test_should_not_flag_sibling_test_using_name_of_class_body_aliased_import() -> None:
    """A probe alias imported inside one test class body binds only inside that
    class scope. A sibling top-level test that takes the same name as a
    parameter must not inherit the alias, so its dotted call on that name does
    not surface a HOME/TMP isolation finding."""
    source = (
        "class TestAlpha:\n"
        "    import tempfile as t\n"
        "    def test_alpha_probe(self) -> None:\n"
        "        assert self.t is not None\n"
        "def test_sibling(t) -> None:\n"
        "    t.mkdtemp()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert not any("test_sibling" in each_issue for each_issue in issues), (
        "a class-body aliased import must not leak into the module-wide alias "
        f"map and flag a sibling test, got: {issues!r}"
    )


def test_should_flag_tempfile_gettempdirb_without_isolation() -> None:
    source = (
        "import tempfile\n"
        "def test_resolves_temp_bytes() -> None:\n"
        "    base = tempfile.gettempdirb()\n"
        "    print(base)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("gettempdirb" in each_issue for each_issue in issues)


def test_should_flag_tempfile_spooled_temporary_file_without_isolation() -> None:
    source = (
        "import tempfile\n"
        "def test_writes_spooled_temp() -> None:\n"
        "    handle = tempfile.SpooledTemporaryFile()\n"
        "    handle.write(b'x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("SpooledTemporaryFile" in each_issue for each_issue in issues)


def test_should_flag_bare_imported_tempfile_spooled_temporary_file() -> None:
    source = (
        "from tempfile import SpooledTemporaryFile\n"
        "def test_writes_spooled_temp() -> None:\n"
        "    handle = SpooledTemporaryFile()\n"
        "    handle.write(b'x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("SpooledTemporaryFile" in each_issue for each_issue in issues)


def test_should_not_flag_named_temporary_file_with_explicit_dir() -> None:
    source = (
        "import tempfile\n"
        "def test_writes_named_temp(tmp_path) -> None:\n"
        "    handle = tempfile.NamedTemporaryFile(dir=tmp_path)\n"
        "    handle.write(b'x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_not_flag_mkdtemp_with_explicit_dir() -> None:
    source = (
        "import tempfile\n"
        "def test_makes_temp_dir(tmp_path) -> None:\n"
        "    holder = tempfile.mkdtemp(dir=tmp_path)\n"
        "    print(holder)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_named_temporary_file_without_dir() -> None:
    source = (
        "import tempfile\n"
        "def test_writes_named_temp() -> None:\n"
        "    handle = tempfile.NamedTemporaryFile()\n"
        "    handle.write(b'x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("NamedTemporaryFile" in each_issue for each_issue in issues)


def test_should_flag_named_temporary_file_with_dir_none() -> None:
    source = (
        "import tempfile\n"
        "def test_writes_named_temp() -> None:\n"
        "    handle = tempfile.NamedTemporaryFile(dir=None)\n"
        "    handle.write(b'x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("NamedTemporaryFile" in each_issue for each_issue in issues)


def test_should_flag_mkdtemp_with_dir_getenv_tmpdir() -> None:
    source = (
        "import os\n"
        "import tempfile\n"
        "def test_makes_temp_dir() -> None:\n"
        "    holder = tempfile.mkdtemp(dir=os.getenv('TMPDIR'))\n"
        "    print(holder)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("mkdtemp" in each_issue for each_issue in issues)


def test_should_flag_named_temporary_file_with_dir_gettempdir() -> None:
    source = (
        "import tempfile\n"
        "def test_writes_named_temp() -> None:\n"
        "    handle = tempfile.NamedTemporaryFile(dir=tempfile.gettempdir())\n"
        "    handle.write(b'x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("NamedTemporaryFile" in each_issue for each_issue in issues)


def test_should_flag_named_temporary_file_with_dir_environ_subscript_tmp() -> None:
    source = (
        "import os\n"
        "import tempfile\n"
        "def test_writes_named_temp() -> None:\n"
        "    handle = tempfile.NamedTemporaryFile(dir=os.environ['TMP'])\n"
        "    handle.write(b'x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("NamedTemporaryFile" in each_issue for each_issue in issues)


def test_should_not_flag_named_temporary_file_with_dir_str_tmp_path() -> None:
    source = (
        "import tempfile\n"
        "def test_writes_named_temp(tmp_path) -> None:\n"
        "    handle = tempfile.NamedTemporaryFile(dir=str(tmp_path))\n"
        "    handle.write(b'x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_not_flag_mkdtemp_with_dir_str_tmp_path() -> None:
    source = (
        "import tempfile\n"
        "def test_makes_temp_dir(tmp_path) -> None:\n"
        "    holder = tempfile.mkdtemp(dir=str(tmp_path))\n"
        "    print(holder)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_still_flag_gettempdir_when_factory_dir_exemption_active() -> None:
    source = (
        "import tempfile\n"
        "def test_reads_shared_temp() -> None:\n"
        "    base = tempfile.gettempdir()\n"
        "    print(base)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("gettempdir" in each_issue for each_issue in issues)


def test_should_allow_home_probe_with_usefixtures_monkeypatch_decorator() -> None:
    source = (
        "import os\n"
        "import pytest\n"
        "@pytest.mark.usefixtures('monkeypatch')\n"
        "def test_reads_home() -> None:\n"
        "    home = os.environ['HOME']\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_allow_path_home_probe_with_usefixtures_monkeypatch_decorator() -> None:
    source = (
        "from pathlib import Path\n"
        "import pytest\n"
        "@pytest.mark.usefixtures('monkeypatch')\n"
        "def test_writes_dotfile() -> None:\n"
        "    home_dir = Path.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_allow_home_probe_with_bare_mark_usefixtures_monkeypatch_decorator() -> None:
    source = (
        "import os\n"
        "from pytest import mark\n"
        "@mark.usefixtures('monkeypatch')\n"
        "def test_reads_home() -> None:\n"
        "    home = os.environ['HOME']\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_allow_home_probe_with_usefixtures_monkeypatch_among_other_fixtures() -> None:
    source = (
        "import os\n"
        "import pytest\n"
        "@pytest.mark.usefixtures('tmp_path', 'monkeypatch')\n"
        "def test_reads_home() -> None:\n"
        "    home = os.environ['HOME']\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_home_probe_with_usefixtures_lacking_monkeypatch() -> None:
    source = (
        "import os\n"
        "import pytest\n"
        "@pytest.mark.usefixtures('tmp_path')\n"
        "def test_reads_home() -> None:\n"
        "    home = os.environ['HOME']\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_flag_home_probe_with_unrelated_marker_decorator() -> None:
    source = (
        "import os\n"
        "import pytest\n"
        "@pytest.mark.parametrize('value', [1, 2])\n"
        "def test_reads_home(value) -> None:\n"
        "    home = os.environ['HOME']\n"
        "    print(home, value)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_order_mixed_probe_types_by_source_line() -> None:
    source = (
        "import os\n"
        "from pathlib import Path\n"
        "import tempfile\n"
        "def test_many_probe_kinds() -> None:\n"
        "    home = os.environ['HOME']\n"
        "    base = tempfile.mkdtemp()\n"
        "    root = Path.home()\n"
        "    target = os.path.expanduser('~/x')\n"
        "    print(home, base, root, target)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    reported_line_numbers = [
        int(each_issue.split(":", maxsplit=1)[0].removeprefix("Line ").strip())
        for each_issue in issues
    ]
    assert reported_line_numbers == sorted(reported_line_numbers)
    assert reported_line_numbers == [5, 6, 7, 8]
