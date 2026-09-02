"""Tests for the PreToolUse dispatcher hosted-hook roster."""

import importlib
import pathlib
import sys

try:
    _HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_HOOKS_ROOT) not in sys.path:
        sys.path.insert(0, str(_HOOKS_ROOT))

    _BLOCKING_DIR = _HOOKS_ROOT / "blocking"
    if str(_BLOCKING_DIR) not in sys.path:
        sys.path.insert(0, str(_BLOCKING_DIR))

    from hooks_constants.pre_tool_use_dispatcher_constants import (
        ALL_HOSTED_HOOK_ENTRIES,
        ALL_IMMEDIATE_HARM_SCRIPT_PATHS,
        ALL_WRITE_AND_EDIT_TOOL_NAMES,
        ALL_WRITE_EDIT_MULTI_EDIT_APPLY_PATCH_TOOL_NAMES,
        ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
        APPLY_PATCH_TOOL_NAME,
        BLOCKING_CRASH_DENY_REASON,
        EDIT_TOOL_NAME,
        MULTI_EDIT_TOOL_NAME,
        WRITE_TOOL_NAME,
    )
    from pre_tool_use_dispatcher import (
        HostedHookResult,
        aggregate_hosted_hook_results,
    )
except ImportError as import_error:
    raise ImportError(
        "test_pre_tool_use_dispatcher_constants: cannot import its sibling modules; "
        "ensure the hooks and blocking directories are importable."
    ) from import_error


def _entry_for(script_relative_path: str):
    matching_entries = [
        each_entry
        for each_entry in ALL_HOSTED_HOOK_ENTRIES
        if each_entry.script_relative_path == script_relative_path
    ]
    return matching_entries[0] if matching_entries else None


def test_roster_includes_duplicate_rmtree_helper_blocker_script_path() -> None:
    all_registered_script_paths = [
        each_entry.script_relative_path for each_entry in ALL_HOSTED_HOOK_ENTRIES
    ]
    assert "blocking/duplicate_rmtree_helper_blocker.py" in all_registered_script_paths, (
        "duplicate_rmtree_helper_blocker must be hosted by the dispatcher so a local "
        "re-definition of the Windows-safe rmtree helper trio is blocked at Write time"
    )


def test_duplicate_rmtree_helper_blocker_applies_to_write_and_edit() -> None:
    entry = _entry_for("blocking/duplicate_rmtree_helper_blocker.py")
    assert entry is not None
    assert WRITE_TOOL_NAME in entry.applicable_tool_names
    assert EDIT_TOOL_NAME in entry.applicable_tool_names


def test_duplicate_rmtree_helper_blocker_is_blocking() -> None:
    entry = _entry_for("blocking/duplicate_rmtree_helper_blocker.py")
    assert entry is not None
    assert entry.is_blocking is True


def test_duplicate_rmtree_helper_blocker_runs_via_runpy() -> None:
    entry = _entry_for("blocking/duplicate_rmtree_helper_blocker.py")
    assert entry is not None
    assert entry.native_module_name is None


def test_windows_rmtree_blocker_still_registered() -> None:
    entry = _entry_for("blocking/windows_rmtree_blocker.py")
    assert entry is not None
    assert entry.applicable_tool_names == ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES


def test_blocking_hook_crash_deny_reason_surfaces_the_constant() -> None:
    crash_result = HostedHookResult(
        exit_code=0,
        captured_stdout="",
        did_crash=True,
        is_blocking=True,
    )
    decision = aggregate_hosted_hook_results([crash_result])
    assert decision.should_deny
    assert BLOCKING_CRASH_DENY_REASON in decision.all_deny_reasons


def test_refactor_guard_is_hosted_as_an_edit_and_multi_edit_advisory_hook() -> None:
    entry = _entry_for("advisory/refactor_guard.py")
    assert entry is not None, (
        "refactor_guard must be hosted by the dispatcher rather than spawning its own process"
    )
    assert entry.applicable_tool_names == frozenset({EDIT_TOOL_NAME, MULTI_EDIT_TOOL_NAME})
    assert entry.is_blocking is False


def test_migration_safety_advisor_is_hosted_as_an_edit_and_multi_edit_advisory_hook() -> None:
    entry = _entry_for("advisory/migration_safety_advisor.py")
    assert entry is not None, (
        "migration_safety_advisor must be hosted by the dispatcher rather than "
        "spawning its own process"
    )
    assert entry.applicable_tool_names == frozenset({EDIT_TOOL_NAME, MULTI_EDIT_TOOL_NAME})
    assert entry.is_blocking is False


def test_every_hosted_script_path_exists_under_the_hooks_root() -> None:
    for each_entry in ALL_HOSTED_HOOK_ENTRIES:
        hosted_script_path = _HOOKS_ROOT / each_entry.script_relative_path
        assert hosted_script_path.is_file(), (
            f"{each_entry.script_relative_path} is on the roster but missing from the hooks tree"
        )


def test_every_native_module_exposes_a_callable_evaluate() -> None:
    nativized_entries = [
        each_entry
        for each_entry in ALL_HOSTED_HOOK_ENTRIES
        if each_entry.native_module_name is not None
    ]
    assert nativized_entries, (
        "the roster must carry at least one nativized hook for this test to lock the contract"
    )
    for each_entry in nativized_entries:
        native_module = importlib.import_module(each_entry.native_module_name)
        evaluate_function = getattr(native_module, "evaluate", None)
        assert callable(evaluate_function), (
            f"{each_entry.native_module_name} must expose a callable named evaluate, "
            "matching the native_module_name docstring contract"
        )


def test_four_way_set_covers_every_mutation_tool_name() -> None:
    assert ALL_WRITE_EDIT_MULTI_EDIT_APPLY_PATCH_TOOL_NAMES == (
        ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES | {APPLY_PATCH_TOOL_NAME}
    )


def test_immediate_harm_hooks_reach_apply_patch() -> None:
    """PII, sensitive-path, existing-file, CODE_RULES, and TDD gates all see apply_patch."""
    for each_script_path in ALL_IMMEDIATE_HARM_SCRIPT_PATHS:
        entry = _entry_for(each_script_path)
        assert entry is not None, f"{each_script_path} must stay on the hosted roster"
        assert APPLY_PATCH_TOOL_NAME in entry.applicable_tool_names, (
            f"{each_script_path} must reach apply_patch for mutation-tool parity"
        )


_ALL_DEFERRED_LINT_SCRIPT_PATHS = (
    "blocking/state_description_blocker.py",
    "blocking/workflow_substitution_slot_blocker.py",
    "blocking/claude_md_orphan_file_blocker.py",
    "blocking/package_inventory_stale_blocker.py",
    "blocking/env_var_table_code_drift_blocker.py",
    "blocking/pytest_testpaths_orphan_blocker.py",
    "blocking/open_questions_in_plans_blocker.py",
    "blocking/docstring_rule_gate_count_blocker.py",
    "blocking/duplicate_rmtree_helper_blocker.py",
    "validation/hook_format_validator.py",
    "blocking/hook_prose_detector_consistency.py",
    "blocking/stale_comment_reference_blocker.py",
    "blocking/subprocess_budget_completeness.py",
    "blocking/windows_rmtree_blocker.py",
    "advisory/refactor_guard.py",
    "advisory/migration_safety_advisor.py",
)


def test_lint_and_advisory_hooks_stay_off_the_apply_patch_roster() -> None:
    """Every hook reaching MultiEdit but not apply_patch fails the same one rule.

    apply_patch reaches only a gate whose violation is already real and
    unrecoverable the moment the call returns: a leaked secret, an exposed
    sensitive path, a blind overwrite, or an untested change landing. Every
    hook named here instead judges the quality of the authored content for a
    consequence the write itself does not cause right now: doc-inventory
    drift, prose or naming style, a future-runtime correctness pattern (an
    unsafe rmtree that only misbehaves on Windows, a subprocess-timeout
    budget the harness reads separately), or an advisory suggestion that
    never denies at all. Each is fixable in a later Edit-tool pass, so none
    needs apply_patch's narrower, deny-only roster.
    """
    for each_script_path in _ALL_DEFERRED_LINT_SCRIPT_PATHS:
        entry = _entry_for(each_script_path)
        assert entry is not None, f"{each_script_path} must stay on the hosted roster"
        assert MULTI_EDIT_TOOL_NAME in entry.applicable_tool_names, (
            f"{each_script_path} must still reach MultiEdit"
        )
        assert APPLY_PATCH_TOOL_NAME not in entry.applicable_tool_names, (
            f"{each_script_path} judges deferred-fixable quality, not immediate harm, "
            "so it must stay off the apply_patch roster"
        )


def test_edit_and_multi_edit_applicable_sets_are_equal() -> None:
    """The Edit roster and the MultiEdit roster name the same hooks.

    Every hook applicable to Edit judges Write's content or an Edit's
    old/new string pair with no dependency on which tool delivered it, so
    the two sets must match exactly. A hook that legitimately stays
    Edit-only is an exception written down here with its reason, not a
    silent gap this test lets back in.
    """
    all_edit_script_paths = {
        each_entry.script_relative_path
        for each_entry in ALL_HOSTED_HOOK_ENTRIES
        if EDIT_TOOL_NAME in each_entry.applicable_tool_names
    }
    all_multi_edit_script_paths = {
        each_entry.script_relative_path
        for each_entry in ALL_HOSTED_HOOK_ENTRIES
        if MULTI_EDIT_TOOL_NAME in each_entry.applicable_tool_names
    }
    assert all_edit_script_paths == all_multi_edit_script_paths, (
        "Edit-only (not MultiEdit): "
        f"{sorted(all_edit_script_paths - all_multi_edit_script_paths)}; "
        "MultiEdit-only (not Edit): "
        f"{sorted(all_multi_edit_script_paths - all_edit_script_paths)}"
    )


def test_multi_edit_widened_hooks_reach_multi_edit() -> None:
    all_multi_edit_widened_script_paths = (
        "blocking/write_existing_file_blocker.py",
        "blocking/code_rules_enforcer.py",
        "blocking/tdd_enforcer.py",
        "blocking/state_description_blocker.py",
    )
    for each_script_path in all_multi_edit_widened_script_paths:
        entry = _entry_for(each_script_path)
        assert entry is not None, f"{each_script_path} must stay on the hosted roster"
        assert MULTI_EDIT_TOOL_NAME in entry.applicable_tool_names, (
            f"{each_script_path} must reach MultiEdit for mutation-tool parity"
        )
