"""Test narrow Edit classification and required rule selection."""

from __future__ import annotations

import ast
import io
import inspect
import json
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

from code_rules_enforcer import (  # noqa: E402
    main,
    validate_content_for_full_gate as validate_content,
)

pytestmark = pytest.mark.usefixtures("ephemeral_exempt_off")


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
        "check_blast_radius_declared",
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


SCOPE_AWARE_RULE_NAMES = ALL_SCOPE_AWARE_RULE_NAMES
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
            "import os\n\n"
            "def fetch_secret() -> str:\n"
            "    return os.environ.get('missing', '')\n"
        ),
        new_fragment=(
            "import os\n\n"
            "def fetch_secret() -> str:\n"
            "    return os.environ['STRIPE_SECRET']\n"
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
            "def render_paths(all_paths: list[str]) -> str:\n"
            "    return ', '.join(all_paths)\n"
        ),
        expected_marker="join",
        rule_name="check_join_separator_string_magic",
    ),
    NarrowEditFixture(
        old_fragment=(
            "def read_count() -> int:\n"
            "    clean_count = 0\n"
            "    return clean_count\n"
        ),
        new_fragment=(
            "def read_count() -> int:\n"
            "    result_count = 0\n"
            "    return result_count\n"
        ),
        expected_marker="result_count",
        rule_name="check_banned_noun_word_boundary",
    ),
    NarrowEditFixture(
        old_fragment=(
            "def check_ready() -> bool:\n"
            "    is_ready = True\n"
            "    return is_ready\n"
        ),
        new_fragment=(
            "def check_ready() -> bool:\n"
            "    ready = True\n"
            "    return ready\n"
        ),
        expected_marker="ready",
        rule_name="check_boolean_naming",
    ),
    NarrowEditFixture(
        old_fragment=(
            "def submit_form() -> None:\n"
            "    if find_and_click('#submit'):\n"
            "        return\n"
        ),
        new_fragment=(
            "def submit_form() -> None:\n"
            "    find_and_click('#submit')\n"
        ),
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


_SCOPE_CARRYING_ATTRIBUTE_NAMES = frozenset({"all_changed_lines", "defer_scope_to_caller"})


def _assignment_target_names(target: ast.expr) -> list[str]:
    """Return the plain names one assignment target binds, Name or Tuple-of-Name."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Tuple):
        return [each.id for each in target.elts if isinstance(each, ast.Name)]
    return []


def _scope_aliases_for_pair(target_names: list[str], all_values: list[ast.expr]) -> dict[str, str]:
    """Return the local-name-to-scope-attribute map one assignment pair contributes."""
    aliases: dict[str, str] = {}
    for each_name, each_value in zip(target_names, all_values):
        if not isinstance(each_value, ast.Attribute):
            continue
        if each_value.attr not in _SCOPE_CARRYING_ATTRIBUTE_NAMES:
            continue
        aliases[each_name] = each_value.attr
    return aliases


def _context_alias_map(function_node: ast.AST) -> dict[str, str]:
    """Map each local name one function binds from ``context.<scope attribute>``.

    A dispatch helper unpacks ``context.all_changed_lines`` and
    ``context.defer_scope_to_caller`` into a short local name (``changed``,
    ``defer``) before passing it on, so a call carrying that local name still
    carries scope, even though the local name spells out none of it.
    """
    aliases: dict[str, str] = {}
    for each_node in ast.walk(function_node):
        if not isinstance(each_node, ast.Assign) or len(each_node.targets) != 1:
            continue
        target_names = _assignment_target_names(each_node.targets[0])
        if not target_names:
            continue
        value = each_node.value
        all_values = value.elts if isinstance(value, ast.Tuple) else [value]
        aliases.update(_scope_aliases_for_pair(target_names, all_values))
    return aliases


def _scope_names_for_reference(reference: ast.AST, aliases: dict[str, str]) -> set[str]:
    """Return the scope-carrying attribute name one AST reference resolves to, if any."""
    if isinstance(reference, ast.Name) and reference.id in aliases:
        return {aliases[reference.id]}
    if isinstance(reference, ast.Attribute) and reference.attr in _SCOPE_CARRYING_ATTRIBUTE_NAMES:
        return {reference.attr}
    return set()


def _referenced_scope_attribute_names(node: ast.AST, aliases: dict[str, str]) -> set[str]:
    """Return every scope-carrying attribute name *node* references, direct or aliased."""
    found: set[str] = set()
    for each_reference in ast.walk(node):
        found.update(_scope_names_for_reference(each_reference, aliases))
    return found


def _fragment_deferred_rule_name(call_node: ast.Call, aliases: dict[str, str]) -> str | None:
    """Return the rule name one ``_fragment_or_deferred_check`` call selects, if scoped."""
    argument_scope_names = {
        each_scope_name
        for each_argument in call_node.args[1:]
        for each_scope_name in _referenced_scope_attribute_names(each_argument, aliases)
    }
    if "defer_scope_to_caller" not in argument_scope_names:
        return None
    if not call_node.args or not isinstance(call_node.args[0], ast.Name):
        return None
    return call_node.args[0].id


def _check_call_rule_name(call_node: ast.Call, aliases: dict[str, str]) -> str | None:
    """Return the rule name one direct ``check_*`` call selects, if it carries scope."""
    func_name = call_node.func.id  # type: ignore[attr-defined]  # caller already narrowed func to ast.Name
    if not func_name.startswith("check_"):
        return None
    all_call_arguments = (*call_node.args, *(each_keyword.value for each_keyword in call_node.keywords))
    argument_scope_names = {
        each_scope_name
        for each_argument in all_call_arguments
        for each_scope_name in _referenced_scope_attribute_names(each_argument, aliases)
    }
    return func_name if argument_scope_names else None


def _rule_names_from_function(function_node: ast.FunctionDef) -> set[str]:
    """Return the check_* names *function_node* calls with scope-carrying arguments."""
    aliases = _context_alias_map(function_node)
    rule_names: set[str] = set()
    for each_call in ast.walk(function_node):
        if not isinstance(each_call, ast.Call) or not isinstance(each_call.func, ast.Name):
            continue
        if each_call.func.id == "_fragment_or_deferred_check":
            rule_name = _fragment_deferred_rule_name(each_call, aliases)
        else:
            rule_name = _check_call_rule_name(each_call, aliases)
        if rule_name is not None:
            rule_names.add(rule_name)
    return rule_names


def _scope_aware_rule_names_from_source() -> frozenset[str]:
    """Return every check_* name dispatched anywhere in the enforcer with scope.

    Walks every function in the enforcer module rather than only
    ``validate_content``, since the extension-issue helper functions hold the
    actual dispatch calls today.
    """
    enforcer_module = inspect.getmodule(validate_content)
    assert enforcer_module is not None
    module_tree = ast.parse(inspect.getsource(enforcer_module))
    all_rule_names: set[str] = set()
    for each_function in ast.walk(module_tree):
        if isinstance(each_function, ast.FunctionDef):
            all_rule_names.update(_rule_names_from_function(each_function))
    return frozenset(all_rule_names)


@pytest.mark.parametrize("narrow_edit_fixture", ALL_REQUIRED_RULE_FIXTURES)
def test_narrow_edit_selects_each_accepted_rule(
    narrow_edit_fixture: NarrowEditFixture,
) -> None:
    all_issues = _validate_narrow_edit(narrow_edit_fixture)
    expected_rule_text = EXPECTED_RULE_TEXT_BY_NAME[narrow_edit_fixture.rule_name]

    assert any(
        narrow_edit_fixture.expected_marker in each_issue
        and expected_rule_text in each_issue
        for each_issue in all_issues
    ), (
        "the changed fragment must select its checker and report its diagnostic marker "
        f"{narrow_edit_fixture.expected_marker!r}, got {all_issues!r}"
    )


def test_scope_aware_inventory_matches_enforcer_dispatch() -> None:
    assert _scope_aware_rule_names_from_source() == ALL_SCOPE_AWARE_RULE_NAMES
def test_narrow_edit_acceptance_set_is_source_backed_and_complete() -> None:
    all_fixture_rule_names = {
        each_fixture.rule_name for each_fixture in ALL_REQUIRED_RULE_FIXTURES
    }

    assert all_fixture_rule_names == NARROW_EDIT_ACCEPTED_RULE_NAMES
    assert NARROW_EDIT_ACCEPTED_RULE_NAMES <= ALL_SCOPE_AWARE_RULE_NAMES

def test_narrow_edit_drops_an_untouched_banned_noun() -> None:
    untouched_source = "OLD_RESULT_PATH = 0\n"
    old_fragment = "PLACEHOLDER_NAME = 0\n"
    new_fragment = "NEW_RESULT_PATH = 0\n"
    issues = validate_content(
        new_fragment,
        PRODUCTION_FILE_PATH,
        old_content=old_fragment,
        full_file_content=untouched_source + new_fragment,
        prior_full_file_content=untouched_source + old_fragment,
    )

    assert any("NEW_RESULT_PATH" in each_issue for each_issue in issues)
    assert not any("OLD_RESULT_PATH" in each_issue for each_issue in issues)


def test_narrow_edit_skips_python_rules_for_a_non_python_target() -> None:
    source = "def process_data() -> None:\n    print('payload')\n"

    issues = validate_content(source, "packages/app/services.txt", old_content="")

    assert issues == []
def _run_edit_stage(
    file_path: Path,
    old_fragment: str,
    new_fragment: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(file_path),
                "old_string": old_fragment,
                "new_string": new_fragment,
            },
        }
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    try:
        main([])
    except SystemExit:
        pass
    return capsys.readouterr().out


def test_edit_entrypoint_reports_an_accepted_rule_for_the_changed_fragment(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    staging_directory = tmp_path_factory.mktemp("narrow_edit")
    source_file = staging_directory / "service.py"
    old_fragment = "def read_count() -> int:\n    clean_count = 0\n    return clean_count\n"
    new_fragment = "def read_count() -> int:\n    result_count = 0\n    return result_count\n"
    source_file.write_text(old_fragment, encoding="utf-8")

    captured_stdout = _run_edit_stage(
        source_file,
        old_fragment,
        new_fragment,
        monkeypatch,
        capsys,
    )

    deny_payload = json.loads(captured_stdout)
    deny_reason = deny_payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "result_count" in deny_reason
