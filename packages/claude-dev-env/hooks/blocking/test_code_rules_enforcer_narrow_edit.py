"""Test narrow Edit classification and required rule selection."""

from __future__ import annotations

import ast
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_enforcer import validate_content

PRODUCTION_FILE_PATH = "packages/app/services.py"


@dataclass(frozen=True)
class NarrowEditFixture:
    """One accepted Edit family with a clean prior fragment and a violation."""

    old_fragment: str
    new_fragment: str
    expected_marker: str
    rule_name: str


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


NARROW_EDIT_ACCEPTED_RULE_NAMES = frozenset(
    {
        "check_string_literal_magic",
        "check_join_separator_string_magic",
        "check_banned_noun_word_boundary",
        "check_boolean_naming",
        "check_ignored_must_check_return",
    }
)


EXPECTED_RULE_TEXT_BY_NAME = {
    "check_string_literal_magic": "string magic value",
    "check_join_separator_string_magic": "string separator",
    "check_banned_noun_word_boundary": "Identifier",
    "check_boolean_naming": "Boolean",
    "check_ignored_must_check_return": "return value",
}


ALL_REQUIRED_RULE_FIXTURES = (
    NarrowEditFixture(
        old_fragment=(
            "import os\n\ndef fetch_secret() -> str:\n    return os.environ.get('missing', '')\n"
        ),
        new_fragment=(
            "import os\n\ndef fetch_secret() -> str:\n    return os.environ['STRIPE_SECRET']\n"
        ),
        expected_marker="STRIPE_SECRET",
        rule_name="check_string_literal_magic",
    ),
    NarrowEditFixture(
        old_fragment=(
            "def render_paths(all_paths: list[str]) -> str:\n"
            "    return JOIN_DELIMITER.join(all_paths)\n"
        ),
        new_fragment=(
            "def render_paths(all_paths: list[str]) -> str:\n    return ', '.join(all_paths)\n"
        ),
        expected_marker="join",
        rule_name="check_join_separator_string_magic",
    ),
    NarrowEditFixture(
        old_fragment=("def read_count() -> int:\n    clean_count = 0\n    return clean_count\n"),
        new_fragment=("def read_count() -> int:\n    result_count = 0\n    return result_count\n"),
        expected_marker="result_count",
        rule_name="check_banned_noun_word_boundary",
    ),
    NarrowEditFixture(
        old_fragment=("def check_ready() -> bool:\n    is_ready = True\n    return is_ready\n"),
        new_fragment=("def check_ready() -> bool:\n    ready = True\n    return ready\n"),
        expected_marker="ready",
        rule_name="check_boolean_naming",
    ),
    NarrowEditFixture(
        old_fragment=(
            "def submit_form() -> None:\n    if find_and_click('#submit'):\n        return\n"
        ),
        new_fragment=("def submit_form() -> None:\n    find_and_click('#submit')\n"),
        expected_marker="find_and_click",
        rule_name="check_ignored_must_check_return",
    ),
)


def _validate_narrow_edit(narrow_edit_fixture: NarrowEditFixture) -> list[str]:
    prior_full_file = narrow_edit_fixture.old_fragment
    post_edit_full_file = narrow_edit_fixture.new_fragment
    return validate_content(
        narrow_edit_fixture.new_fragment,
        PRODUCTION_FILE_PATH,
        old_content=narrow_edit_fixture.old_fragment,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )


@pytest.mark.parametrize("narrow_edit_fixture", ALL_REQUIRED_RULE_FIXTURES)
def test_narrow_edit_selects_each_accepted_rule(
    narrow_edit_fixture: NarrowEditFixture,
) -> None:
    all_issues = _validate_narrow_edit(narrow_edit_fixture)
    expected_rule_text = EXPECTED_RULE_TEXT_BY_NAME[narrow_edit_fixture.rule_name]

    assert any(
        narrow_edit_fixture.expected_marker in each_issue and expected_rule_text in each_issue
        for each_issue in all_issues
    ), (
        "the changed fragment must select its checker and report its diagnostic marker "
        f"{narrow_edit_fixture.expected_marker!r}, got {all_issues!r}"
    )


def test_narrow_edit_acceptance_set_is_source_backed_and_complete() -> None:
    all_fixture_rule_names = {each_fixture.rule_name for each_fixture in ALL_REQUIRED_RULE_FIXTURES}

    assert all_fixture_rule_names == NARROW_EDIT_ACCEPTED_RULE_NAMES
    assert NARROW_EDIT_ACCEPTED_RULE_NAMES <= ALL_SCOPE_AWARE_RULE_NAMES


def test_narrow_edit_skips_python_rules_for_a_non_python_target() -> None:
    source = "def process_data() -> None:\n    print('payload')\n"

    issues = validate_content(source, "packages/app/services.txt", old_content="")

    assert issues == []
