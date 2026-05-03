"""Tests for sys.path.insert dedup-guard rule.

Bot reviewers on PR #289 flagged grant_project_claude_permissions.py:13
and revoke_project_claude_permissions.py for unconditionally calling
sys.path.insert(0, X) without checking whether X was already present.
The convention in the rest of the repo is to guard the call with
`if str(X) not in sys.path:` (or equivalent) to avoid pushing the
same path repeatedly when modules get reloaded.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys


_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIRECTORY / "code_rules_enforcer.py",
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(_hook_module)
check_sys_path_insert_deduplication_guard = _hook_module.check_sys_path_insert_deduplication_guard


PRODUCTION_FILE_PATH = "packages/app/services/loader.py"
TEST_FILE_PATH = "packages/app/tests/test_loader.py"


def test_should_flag_unguarded_module_level_insert() -> None:
    source = (
        "import sys\n"
        "from pathlib import Path\n"
        "REPOSITORY_ROOT = Path(__file__).resolve().parent\n"
        "sys.path.insert(0, str(REPOSITORY_ROOT))\n"
    )
    issues = check_sys_path_insert_deduplication_guard(source, PRODUCTION_FILE_PATH)
    assert any("sys.path.insert" in each_issue for each_issue in issues), (
        f"Expected unguarded sys.path.insert flagged, got: {issues}"
    )


def test_should_not_flag_when_preceded_by_membership_guard() -> None:
    source = (
        "import sys\n"
        "from pathlib import Path\n"
        "REPOSITORY_ROOT = str(Path(__file__).resolve().parent)\n"
        "if REPOSITORY_ROOT not in sys.path:\n"
        "    sys.path.insert(0, REPOSITORY_ROOT)\n"
    )
    issues = check_sys_path_insert_deduplication_guard(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Guarded insert (if X not in sys.path) must not be flagged, got: {issues}"
    )


def test_should_flag_unguarded_function_local_insert() -> None:
    source = (
        "import sys\ndef configure() -> None:\n    sys.path.insert(0, '/some/path')\n"
    )
    issues = check_sys_path_insert_deduplication_guard(source, PRODUCTION_FILE_PATH)
    assert any("sys.path.insert" in each_issue for each_issue in issues), (
        f"Function-local unguarded insert must be flagged, got: {issues}"
    )


def test_should_not_flag_function_local_when_guarded() -> None:
    source = (
        "import sys\n"
        "def configure() -> None:\n"
        "    target = '/some/path'\n"
        "    if target not in sys.path:\n"
        "        sys.path.insert(0, target)\n"
    )
    issues = check_sys_path_insert_deduplication_guard(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Guarded function-local insert must pass, got: {issues}"


def test_should_not_flag_sys_path_append_or_extend() -> None:
    source = (
        "import sys\nsys.path.append('/some/path')\nsys.path.extend(['/a', '/b'])\n"
    )
    issues = check_sys_path_insert_deduplication_guard(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"This rule targets sys.path.insert specifically, append/extend exempt, got: {issues}"
    )


def test_should_skip_test_files() -> None:
    source = "import sys\nsys.path.insert(0, '/some/path')\n"
    issues = check_sys_path_insert_deduplication_guard(source, TEST_FILE_PATH)
    assert issues == [], (
        f"Test files exempt — fixtures often manipulate sys.path, got: {issues}"
    )


def test_should_handle_syntax_error_gracefully() -> None:
    source = "import sys\nsys.path.insert(\n    not python\n"
    issues = check_sys_path_insert_deduplication_guard(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Parse failure must return empty, got: {issues}"


def test_should_recognize_str_call_around_path_in_guard() -> None:
    source = (
        "import sys\n"
        "from pathlib import Path\n"
        "ROOT = Path('/x')\n"
        "if str(ROOT) not in sys.path:\n"
        "    sys.path.insert(0, str(ROOT))\n"
    )
    issues = check_sys_path_insert_deduplication_guard(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"str(ROOT) wrapped in both guard and insert must not flag, got: {issues}"
    )


def test_should_include_line_number_in_issue() -> None:
    source = "import sys\n\n\nsys.path.insert(0, '/x')\n"
    issues = check_sys_path_insert_deduplication_guard(source, PRODUCTION_FILE_PATH)
    assert any("Line 4" in each_issue for each_issue in issues), (
        f"Expected line 4 reference, got: {issues}"
    )


def test_should_flag_inverted_membership_guard_inserting_in_then_branch() -> None:
    source = (
        "import sys\n"
        "TARGET = '/some/path'\n"
        "if TARGET in sys.path:\n"
        "    sys.path.insert(0, TARGET)\n"
    )
    issues = check_sys_path_insert_deduplication_guard(source, PRODUCTION_FILE_PATH)
    assert any("sys.path.insert" in each_issue for each_issue in issues), (
        "`if X in sys.path: sys.path.insert(0, X)` inserts a duplicate when X "
        f"is already present; only `not in` guards then-branch inserts. Got: {issues}"
    )


def test_should_flag_inverted_membership_guard_with_str_wrapper() -> None:
    source = (
        "import sys\n"
        "from pathlib import Path\n"
        "ROOT = Path('/x')\n"
        "if str(ROOT) in sys.path:\n"
        "    sys.path.insert(0, str(ROOT))\n"
    )
    issues = check_sys_path_insert_deduplication_guard(source, PRODUCTION_FILE_PATH)
    assert any("sys.path.insert" in each_issue for each_issue in issues), (
        f"Inverted membership guard with str() wrapper must still flag, got: {issues}"
    )
