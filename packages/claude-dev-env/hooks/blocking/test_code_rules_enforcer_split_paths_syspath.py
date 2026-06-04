"""Behavior tests for the code_rules_paths_syspath code-rules check module."""

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

from code_rules_paths_syspath import (  # noqa: E402
    HARDCODED_USER_PATH_GUIDANCE,
    HARDCODED_USER_PATH_PATTERN,
    MAX_HARDCODED_USER_PATH_ISSUES,
    check_sys_path_insert_deduplication_guard,
)

from hooks_constants.hardcoded_user_path_constants import (  # noqa: E402
    HARDCODED_USER_PATH_GUIDANCE as config_hardcoded_user_path_guidance,
)
from hooks_constants.hardcoded_user_path_constants import (  # noqa: E402
    HARDCODED_USER_PATH_PATTERN as config_hardcoded_user_path_pattern,
)
from hooks_constants.hardcoded_user_path_constants import (  # noqa: E402
    MAX_HARDCODED_USER_PATH_ISSUES as config_max_hardcoded_user_path_issues,
)

code_rules_enforcer = SimpleNamespace(
    HARDCODED_USER_PATH_GUIDANCE=HARDCODED_USER_PATH_GUIDANCE,
    HARDCODED_USER_PATH_PATTERN=HARDCODED_USER_PATH_PATTERN,
    MAX_HARDCODED_USER_PATH_ISSUES=MAX_HARDCODED_USER_PATH_ISSUES,
    check_sys_path_insert_deduplication_guard=check_sys_path_insert_deduplication_guard,
)


SYS_PATH_INSERT_HOOK_INFRASTRUCTURE_FILE_PATH = "/repo/.claude/hooks/blocking/some_hook.py"

SYS_PATH_INSERT_PRODUCTION_FILE_PATH = "packages/app/services/loader.py"


def test_should_reexport_hardcoded_user_path_pattern_from_config() -> None:
    assert code_rules_enforcer.HARDCODED_USER_PATH_PATTERN is config_hardcoded_user_path_pattern


def test_should_reexport_max_hardcoded_user_path_issues_from_config() -> None:
    assert code_rules_enforcer.MAX_HARDCODED_USER_PATH_ISSUES == config_max_hardcoded_user_path_issues


def test_should_reexport_hardcoded_user_path_guidance_from_config() -> None:
    assert code_rules_enforcer.HARDCODED_USER_PATH_GUIDANCE == config_hardcoded_user_path_guidance


def test_sys_path_insert_should_flag_mismatched_guard_path() -> None:
    source = (
        "import sys\n"
        'if "wrong_path" not in sys.path:\n'
        '    sys.path.insert(0, "actual_path")\n'
    )
    issues = code_rules_enforcer.check_sys_path_insert_deduplication_guard(
        source, SYS_PATH_INSERT_PRODUCTION_FILE_PATH
    )
    assert any("sys.path.insert" in each_issue for each_issue in issues), (
        "Guard testing a different value than what is inserted must be flagged, "
        f"got: {issues}"
    )


def test_sys_path_insert_should_not_flag_matching_guard_path() -> None:
    source = (
        "import sys\n"
        'if "correct_path" not in sys.path:\n'
        '    sys.path.insert(0, "correct_path")\n'
    )
    issues = code_rules_enforcer.check_sys_path_insert_deduplication_guard(
        source, SYS_PATH_INSERT_PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Guard testing the same value that is inserted must not be flagged, got: {issues}"
    )


def test_sys_path_insert_should_not_flag_guarded_insert_in_class_body() -> None:
    source = (
        "import sys\n"
        "class Configurator:\n"
        "    target = '/some/path'\n"
        "    if target not in sys.path:\n"
        "        sys.path.insert(0, target)\n"
    )
    issues = code_rules_enforcer.check_sys_path_insert_deduplication_guard(
        source, SYS_PATH_INSERT_PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Guarded sys.path.insert directly in a class body must not be flagged, got: {issues}"
    )


def test_sys_path_insert_should_skip_hook_infrastructure_files() -> None:
    source = "import sys\nsys.path.insert(0, '/some/path')\n"
    issues = code_rules_enforcer.check_sys_path_insert_deduplication_guard(
        source, SYS_PATH_INSERT_HOOK_INFRASTRUCTURE_FILE_PATH
    )
    assert issues == [], (
        f"Hook infrastructure files are exempt from this rule, got: {issues}"
    )
