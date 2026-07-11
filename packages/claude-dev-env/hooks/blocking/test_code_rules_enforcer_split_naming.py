"""Behavior tests for the code_rules_naming_collection code-rules check module."""

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

from code_rules_naming_collection import (  # noqa: E402
    MAX_STUTTERING_PREFIX_ISSUES,
    STUTTERING_ALL_PREFIX_PATTERN,
    check_loop_variable_naming,
    check_stuttering_collection_prefix,
)

from hooks_constants.stuttering_check_config import (  # noqa: E402
    MAX_STUTTERING_PREFIX_ISSUES as config_max_stuttering_prefix_issues,
)
from hooks_constants.stuttering_check_config import (  # noqa: E402
    STUTTERING_ALL_PREFIX_PATTERN as config_stuttering_all_prefix_pattern,
)

code_rules_enforcer = SimpleNamespace(
    MAX_STUTTERING_PREFIX_ISSUES=MAX_STUTTERING_PREFIX_ISSUES,
    STUTTERING_ALL_PREFIX_PATTERN=STUTTERING_ALL_PREFIX_PATTERN,
    check_loop_variable_naming=check_loop_variable_naming,
    check_stuttering_collection_prefix=check_stuttering_collection_prefix,
)


LOOP_NAMING_PRODUCTION_FILE_PATH = "packages/app/services/loop_naming.py"


def test_check_loop_variable_naming_flags_missing_each_prefix() -> None:
    source = (
        "def consume() -> None:\n"
        "    for marker in []:\n"
        "        return None\n"
    )
    issues = code_rules_enforcer.check_loop_variable_naming(
        source, LOOP_NAMING_PRODUCTION_FILE_PATH
    )
    assert any("marker" in each_issue for each_issue in issues), (
        f"Expected 'marker' loop variable flagged, got: {issues}"
    )


def test_stuttering_collection_prefix_flags_function_name_loop1_1() -> None:
    source = "def all_all_process() -> None:\n    return None\n"
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, "packages/app/services/foo.py"
    )
    assert any("all_all_process" in each_issue for each_issue in issues), (
        f"loop1-1: stuttering function name must be flagged, got: {issues}"
    )


def test_stuttering_collection_prefix_flags_with_as_binding_loop3_1() -> None:
    source = "def f() -> None:\n    with open('x') as all_all_context:\n        pass\n"
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, "packages/app/services/foo.py"
    )
    assert any("all_all_context" in each_issue for each_issue in issues), (
        f"loop3-1: stuttering with-as binding must be flagged, got: {issues}"
    )


def test_stuttering_collection_prefix_flags_except_as_binding_loop3_1() -> None:
    source = (
        "def f() -> None:\n"
        "    try:\n"
        "        pass\n"
        "    except Exception as all_all_error:\n"
        "        pass\n"
    )
    issues = code_rules_enforcer.check_stuttering_collection_prefix(
        source, "packages/app/services/foo.py"
    )
    assert any("all_all_error" in each_issue for each_issue in issues), (
        f"loop3-1: stuttering except-as binding must be flagged, got: {issues}"
    )


def test_stuttering_constants_live_under_config_subpackage() -> None:
    """Stuttering-prefix constants must be sourced from the hooks-tree config package.

    Per CODE_RULES, module-level UPPER_SNAKE constants must live under a
    directory segment named ``config``. This test pins the move so the
    constants cannot regress to inline definition at the enforcer module's
    top level. The enforcer's own bootstrap inserts the hooks tree onto
    ``sys.path`` so ``config.stuttering_check_config`` resolves at runtime.
    """
    assert (
        code_rules_enforcer.STUTTERING_ALL_PREFIX_PATTERN
        is config_stuttering_all_prefix_pattern
    ), "Enforcer must reuse the hooks-tree config STUTTERING_ALL_PREFIX_PATTERN object"
    assert (
        code_rules_enforcer.MAX_STUTTERING_PREFIX_ISSUES
        == config_max_stuttering_prefix_issues
    ), "Enforcer must reuse the hooks-tree config MAX_STUTTERING_PREFIX_ISSUES value"
