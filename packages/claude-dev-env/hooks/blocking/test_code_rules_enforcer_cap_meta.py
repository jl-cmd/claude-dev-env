"""Meta-test asserting every check_* function in code_rules_enforcer follows the cap convention.

Bot reviewers on PR #232 flagged check_existence_check_tests,
check_constant_equality_tests, and check_unused_optional_parameters for
returning unbounded issue lists, which produces a spammy blocking
payload when a single file has many violations of the same kind.

The convention is: every check_* function should either apply an
explicit cap (a constant containing 'MAX_' AND a `break`/early return
on length), or be explicitly listed below as a known-uncapped check
along with the reason. New check_* functions added to the module
without consideration will trip this test.
"""

from __future__ import annotations

import importlib.util
import inspect
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

KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW: frozenset[str] = frozenset(
    {
        "check_boolean_naming",
        "check_collection_prefix",
        "check_comment_changes",
        "check_comments_javascript",
        "check_comments_python",
        "check_constant_equality_tests",
        "check_constants_outside_config",
        "check_constants_outside_config_advisory",
        "check_duplicated_format_patterns",
        "check_e2e_test_naming",
        "check_existence_check_tests",
        "check_file_global_constants_use_count",
        "check_fstring_structural_literals",
        "check_imports_at_top",
        "check_incomplete_mocks",
        "check_inline_literal_collections",
        "check_library_print",
        "check_logging_fstrings",
        "check_loop_variable_naming",
        "check_magic_values",
        "check_parameter_annotations",
        "check_return_annotations",
        "check_skip_decorators_in_tests",
        "check_string_literal_magic",
        "check_type_escape_hatches",
        "check_unused_optional_parameters",
        "check_windows_api_none",
    }
)

CAP_TOKEN_FRAGMENTS: tuple[str, ...] = ("MAX_", "islice")


def _all_check_function_names() -> list[str]:
    return [
        each_attribute_name
        for each_attribute_name in dir(_hook_module)
        if each_attribute_name.startswith("check_")
        and callable(getattr(_hook_module, each_attribute_name))
    ]


def _function_source_contains_cap(function_name: str) -> bool:
    function_object = getattr(_hook_module, function_name)
    function_source = inspect.getsource(function_object)
    return any(
        each_fragment in function_source for each_fragment in CAP_TOKEN_FRAGMENTS
    )


def test_every_check_function_either_caps_or_is_explicitly_pending() -> None:
    all_check_names = set(_all_check_function_names())
    capped_check_names = {
        each_name
        for each_name in all_check_names
        if _function_source_contains_cap(each_name)
    }
    uncapped_check_names = all_check_names - capped_check_names
    unexpected_uncapped = uncapped_check_names - KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW
    assert unexpected_uncapped == set(), (
        f"New check_* functions added without a cap and not on the pending-review list: "
        f"{sorted(unexpected_uncapped)}. Either apply a MAX_*_ISSUES cap with a break/return, "
        f"or explicitly add the function to KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW with a "
        f"reason in the test header docstring."
    )


def test_pending_review_set_does_not_grow_silently() -> None:
    all_check_names = set(_all_check_function_names())
    stale_pending = KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW - all_check_names
    assert stale_pending == set(), (
        f"KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW lists functions that no longer exist: "
        f"{sorted(stale_pending)}. Either restore the function or remove it from the list."
    )


def test_already_capped_checks_stay_capped() -> None:
    capped_baseline: frozenset[str] = frozenset(
        {
            "check_banned_identifiers",
        }
    )
    for each_name in capped_baseline:
        assert _function_source_contains_cap(each_name), (
            f"{each_name} previously had a cap reference and now does not. "
            f"Caps protect blocking output from spamming reviewers — restore it."
        )
