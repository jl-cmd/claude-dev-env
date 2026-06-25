"""Meta-test asserting every check_* function in code_rules_enforcer follows the cap convention.

Bot reviewers on PR #232 flagged check_existence_check_tests,
check_constant_equality_tests, and check_unused_optional_parameters for
returning unbounded issue lists, which produces a spammy blocking
payload when a single file has many violations of the same kind.

The convention is: every check_* function should either apply an
explicit cap (the meta-test treats a function as capped when its source
contains a ``MAX_`` constant name or uses ``itertools.islice`` for bounded
iteration), or appear in DIFF_SCOPED_CHECK_FUNCTION_NAMES when its blocking
payload is scoped by the diff: on a terminal Edit (``all_changed_lines`` is a
set) only violations whose span intersects the edit's changed lines block, so
untouched code cannot spam the payload; on a new-file or full-file write
(``all_changed_lines is None``) every violation is reported because the author
wrote the whole file. The scoping bounds the Edit payload to the change the
author is making rather than imposing a fixed ceiling. A function may instead
be explicitly listed in KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW along with the
reason, or appear in VOID_ADVISORY_CHECK_FUNCTION_NAMES when the function is
annotated ``-> None`` and never contributes issues to the blocking payload
(stderr-only advisories). New check_* functions added to the module without
consideration will trip this test.
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

VOID_ADVISORY_CHECK_FUNCTION_NAMES: frozenset[str] = frozenset(
    {
        "check_duplicated_format_patterns",
        "check_flag_gated_scenario_test_naming",
        "check_incomplete_mocks",
    }
)

DIFF_SCOPED_CHECK_FUNCTION_NAMES: frozenset[str] = frozenset(
    {
        "check_banned_noun_word_boundary",
        "check_function_length",
        "check_tests_use_isolated_filesystem_paths",
    }
)

KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW: frozenset[str] = frozenset(
    {
        "check_boolean_naming",
        "check_collection_prefix",
        "check_comment_changes",
        "check_constant_equality_tests",
        "check_constants_outside_config",
        "check_constants_outside_config_advisory",
        "check_existence_check_tests",
        "check_file_global_constants_use_count",
        "check_imports_at_top",
        "check_inline_literal_collections",
        "check_known_pytest_fixture_annotations",
        "check_library_print",
        "check_loop_variable_naming",
        "check_parameter_annotations",
        "check_return_annotations",
        "check_skip_decorators_in_tests",
        "check_string_literal_magic",
        "check_unused_known_pytest_fixture_parameters",
        "check_unused_optional_parameters",
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
    unexpected_uncapped = (
        uncapped_check_names
        - KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW
        - VOID_ADVISORY_CHECK_FUNCTION_NAMES
        - DIFF_SCOPED_CHECK_FUNCTION_NAMES
    )
    assert unexpected_uncapped == set(), (
        f"New check_* functions added without a cap and not on the pending-review list: "
        f"{sorted(unexpected_uncapped)}. Either add a MAX_* cap or islice-bounded loop in "
        f"source, or add the function to DIFF_SCOPED_CHECK_FUNCTION_NAMES when its blocking "
        f"payload is bounded by diff scoping, or explicitly add it to "
        f"KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW with a reason in the test header docstring, or "
        f"list it in VOID_ADVISORY_CHECK_FUNCTION_NAMES when it is annotated -> None and emits "
        f"only stderr guidance."
    )


def test_pending_review_set_does_not_grow_silently() -> None:
    all_check_names = set(_all_check_function_names())
    stale_pending = KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW - all_check_names
    assert stale_pending == set(), (
        f"KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW lists functions that no longer exist: "
        f"{sorted(stale_pending)}. Either restore the function or remove it from the list."
    )


def test_pending_review_set_excludes_functions_that_already_match_cap_heuristic() -> None:
    all_check_names = set(_all_check_function_names())
    pending_that_exist = KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW & all_check_names
    capped_but_still_pending = {
        each_name
        for each_name in pending_that_exist
        if _function_source_contains_cap(each_name)
    }
    assert capped_but_still_pending == set(), (
        f"KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW must not list checks that already satisfy the "
        f"cap heuristic (would hide a later cap removal): {sorted(capped_but_still_pending)}. "
        f"Remove those names from the pending set after capping."
    )


def test_void_advisory_checks_are_registered_and_disjoint() -> None:
    all_check_names = set(_all_check_function_names())
    assert VOID_ADVISORY_CHECK_FUNCTION_NAMES <= all_check_names, (
        f"VOID_ADVISORY_CHECK_FUNCTION_NAMES references missing names: "
        f"{sorted(VOID_ADVISORY_CHECK_FUNCTION_NAMES - all_check_names)}"
    )
    for each_name in VOID_ADVISORY_CHECK_FUNCTION_NAMES:
        function_object = getattr(_hook_module, each_name)
        return_annotation = inspect.signature(function_object).return_annotation
        assert return_annotation is None, (
            f"VOID_ADVISORY_CHECK_FUNCTION_NAMES must list only advisory-only checks annotated "
            f"with -> None (stderr-only, never block). {each_name!r} has return annotation "
            f"{return_annotation!r}."
        )
    overlap = VOID_ADVISORY_CHECK_FUNCTION_NAMES & KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW
    assert overlap == set(), (
        f"Void-advisory checks must not also appear on the uncapped pending list: "
        f"{sorted(overlap)}"
    )


def test_diff_scoped_checks_are_registered_and_disjoint() -> None:
    all_check_names = set(_all_check_function_names())
    assert DIFF_SCOPED_CHECK_FUNCTION_NAMES <= all_check_names, (
        f"DIFF_SCOPED_CHECK_FUNCTION_NAMES references missing names: "
        f"{sorted(DIFF_SCOPED_CHECK_FUNCTION_NAMES - all_check_names)}"
    )
    for each_name in DIFF_SCOPED_CHECK_FUNCTION_NAMES:
        function_source = inspect.getsource(getattr(_hook_module, each_name))
        assert "all_changed_lines" in function_source or "defer_scope_to_caller" in function_source, (
            f"DIFF_SCOPED_CHECK_FUNCTION_NAMES must list only checks bounded by diff scoping. "
            f"{each_name!r} references neither all_changed_lines nor defer_scope_to_caller."
        )
    pending_overlap = DIFF_SCOPED_CHECK_FUNCTION_NAMES & KNOWN_UNCAPPED_CHECKS_PENDING_REVIEW
    void_overlap = DIFF_SCOPED_CHECK_FUNCTION_NAMES & VOID_ADVISORY_CHECK_FUNCTION_NAMES
    assert pending_overlap == set() and void_overlap == set(), (
        f"Diff-scoped checks must not also appear on the pending or void-advisory lists: "
        f"pending {sorted(pending_overlap)}, void {sorted(void_overlap)}"
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
