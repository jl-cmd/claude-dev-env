"""Test narrow Edit classification and required rule selection."""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_enforcer import validate_content

ALL_SCOPE_AWARE_RULE_NAMES = frozenset(
    {
        "check_import_block_sorted",
        "check_magic_values",
        "check_duplicate_function_body_across_files",
        "check_same_file_inline_duplicate_body",
        "check_banned_identifiers",
        "check_banned_noun_word_boundary",
        "check_docstring_runon_sentence",
        "check_docstring_prose_wall_without_illustration",
        "check_boolean_naming",
        "check_ignored_must_check_return",
        "check_tests_use_isolated_filesystem_paths",
        "check_return_annotations",
        "check_function_length",
        "check_public_function_missing_paired_test",
        "check_join_separator_string_magic",
        "check_string_literal_magic",
        "check_js_boolean_naming",
        "check_js_banned_identifiers",
        "check_js_bare_flag_return_directive",
    }
)


def _scope_aware_rule_names_from_source() -> frozenset[str]:
    source_tree = ast.parse(inspect.getsource(validate_content))
    all_rule_names: set[str] = set()
    for each_call in ast.walk(source_tree):
        if not isinstance(each_call, ast.Call):
            continue
        if not isinstance(each_call.func, ast.Name):
            continue
        if each_call.func.id == "_fragment_or_deferred_check":
            all_argument_names = {
                each_name.id
                for each_argument in each_call.args[1:]
                for each_name in ast.walk(each_argument)
                if isinstance(each_name, ast.Name)
            }
            if (
                "defer_scope_to_caller" in all_argument_names
                and each_call.args
                and isinstance(each_call.args[0], ast.Name)
            ):
                all_rule_names.add(each_call.args[0].id)
            continue
        if not each_call.func.id.startswith("check_"):
            continue
        all_argument_names = {
            each_name.id
            for each_argument in each_call.args
            for each_name in ast.walk(each_argument)
            if isinstance(each_name, ast.Name)
        }
        all_argument_names.update(
            each_name.id
            for each_keyword in each_call.keywords
            for each_name in ast.walk(each_keyword.value)
            if isinstance(each_name, ast.Name)
        )
        if (
            "all_changed_lines" in all_argument_names
            or "defer_scope_to_caller" in all_argument_names
        ):
            all_rule_names.add(each_call.func.id)
    return frozenset(all_rule_names)


def test_scope_aware_inventory_matches_enforcer_dispatch() -> None:
    assert _scope_aware_rule_names_from_source() == ALL_SCOPE_AWARE_RULE_NAMES
