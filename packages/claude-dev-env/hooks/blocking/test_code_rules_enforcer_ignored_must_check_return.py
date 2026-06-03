"""Tests for check_ignored_must_check_return — discarded must-check outcomes.

A bare-statement call to a function in ALL_MUST_CHECK_RETURN_FUNCTION_NAMES
discards the only failure signal it produces. An assigned or branched-on
call is exempt; only bare ``ast.Expr`` calls are flagged.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


def check_ignored_must_check_return(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_ignored_must_check_return(content, file_path)


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/clicker.py"
TEST_FILE_PATH = "/project/src/test_clicker.py"


def test_should_flag_bare_find_and_click_call() -> None:
    source = "def step() -> None:\n    find_and_click('#submit')\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert any("find_and_click" in each for each in issues), (
        f"Expected discarded-return flag for find_and_click, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_flag_bare_write_outcome_call() -> None:
    source = "def step() -> None:\n    write_outcome('done')\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert any("write_outcome" in each for each in issues), (
        f"Expected discarded-return flag for write_outcome, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_flag_attribute_call_with_must_check_name() -> None:
    source = "def step() -> None:\n    self.find_and_click('#submit')\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 1, f"Attribute call terminal name must be resolved, got: {issues!r}"


def test_should_not_flag_assigned_find_and_click() -> None:
    source = "def step() -> None:\n    clicked = find_and_click('#submit')\n    print(clicked)\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Assigned call must not be flagged, got: {issues!r}"


def test_should_not_flag_branched_find_and_click() -> None:
    source = "def step() -> None:\n    if find_and_click('#submit'):\n        pass\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Branched-on call must not be flagged, got: {issues!r}"


def test_should_flag_bare_awaited_find_and_click_call() -> None:
    source = "async def step() -> None:\n    await find_and_click('#x')\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert any("find_and_click" in each for each in issues), (
        f"Expected discarded-return flag for awaited find_and_click, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_not_flag_assigned_awaited_find_and_click() -> None:
    source = (
        "async def step() -> None:\n"
        "    clicked = await find_and_click('#x')\n"
        "    print(clicked)\n"
    )
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Assigned awaited call must not be flagged, got: {issues!r}"


def test_should_not_flag_branched_awaited_find_and_click() -> None:
    source = "async def step() -> None:\n    if await find_and_click('#x'):\n        pass\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Branched-on awaited call must not be flagged, got: {issues!r}"


def test_should_not_flag_unrelated_bare_call() -> None:
    source = "def step() -> None:\n    print('hello')\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Unrelated call must not be flagged, got: {issues!r}"


def test_should_skip_test_file() -> None:
    source = "def step() -> None:\n    find_and_click('#submit')\n"
    issues = check_ignored_must_check_return(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_ignored_must_check_return("def step(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_validate_content_surfaces_discarded_return() -> None:
    source = "def step() -> None:\n    find_and_click('#submit')\n"
    issues = validate_content(source, PRODUCTION_FILE_PATH, old_content="")
    matching_issues = [each for each in issues if "find_and_click" in each]
    assert matching_issues, (
        f"Expected validate_content to surface the discarded-return issue, got: {issues!r}"
    )


EDIT_FULL_MODULE_SOURCE = (
    "async def step() -> None:\n"
    "    await find_and_click('#x')\n"
)
AWAITED_CALL_LINE_NUMBER = 2
UNCHANGED_LINE_NUMBER = 1


def test_should_flag_when_changed_line_covers_the_bare_await() -> None:
    all_changed_lines = {AWAITED_CALL_LINE_NUMBER}
    issues = code_rules_enforcer.check_ignored_must_check_return(
        EDIT_FULL_MODULE_SOURCE,
        PRODUCTION_FILE_PATH,
        all_changed_lines,
        False,
    )
    assert len(issues) == 1, (
        f"An Edit touching the bare await line must surface exactly one issue, got: {issues!r}"
    )
    assert "find_and_click" in issues[0]


def test_should_not_flag_when_changed_line_excludes_the_bare_await() -> None:
    all_changed_lines = {UNCHANGED_LINE_NUMBER}
    issues = code_rules_enforcer.check_ignored_must_check_return(
        EDIT_FULL_MODULE_SOURCE,
        PRODUCTION_FILE_PATH,
        all_changed_lines,
        False,
    )
    assert issues == [], (
        f"A pre-existing violation on an unedited line must not block the edit, got: {issues!r}"
    )


PRE_EXISTING_BARE_CALL_COUNT = 5
EDITED_BARE_CALL_LINE_NUMBER = PRE_EXISTING_BARE_CALL_COUNT + 2


def _build_module_with_pre_existing_violations_before_the_edit() -> str:
    all_signature_lines = ["async def step() -> None:"]
    all_pre_existing_call_lines = [
        f"    await find_and_click('#x{each_index}')"
        for each_index in range(PRE_EXISTING_BARE_CALL_COUNT)
    ]
    edited_call_line = "    await find_and_click('#edited')"
    all_lines = all_signature_lines + all_pre_existing_call_lines + [edited_call_line]
    return "\n".join(all_lines) + "\n"


def test_should_flag_edited_line_even_when_cap_worth_of_violations_precede_it() -> None:
    source = _build_module_with_pre_existing_violations_before_the_edit()
    all_changed_lines = {EDITED_BARE_CALL_LINE_NUMBER}
    issues = code_rules_enforcer.check_ignored_must_check_return(
        source,
        PRODUCTION_FILE_PATH,
        all_changed_lines,
        False,
    )
    assert len(issues) == 1, (
        "Collecting every violation before scoping must surface the edited-line "
        f"violation even with a cap's worth of earlier out-of-scope calls, got: {issues!r}"
    )
    assert f"Line {EDITED_BARE_CALL_LINE_NUMBER}:" in issues[0], (
        f"The single issue must name the edited line {EDITED_BARE_CALL_LINE_NUMBER}, got: {issues!r}"
    )


def _build_module_with_more_than_cap_bare_calls() -> tuple[str, int]:
    bare_call_count = code_rules_enforcer.MAX_IGNORED_MUST_CHECK_RETURN_ISSUES + 3
    all_signature_lines = ["async def step() -> None:"]
    all_call_lines = [
        f"    await find_and_click('#x{each_index}')"
        for each_index in range(bare_call_count)
    ]
    source = "\n".join(all_signature_lines + all_call_lines) + "\n"
    return source, bare_call_count


def test_deferred_scope_returns_every_violation_uncapped() -> None:
    source, bare_call_count = _build_module_with_more_than_cap_bare_calls()
    issues = code_rules_enforcer.check_ignored_must_check_return(
        source,
        PRODUCTION_FILE_PATH,
        None,
        True,
    )
    assert len(issues) == bare_call_count, (
        "With defer_scope_to_caller=True the gate must see every violation uncapped "
        f"so it can scope by added line, got: {issues!r}"
    )


def test_terminal_scope_caps_violations_at_the_module_limit() -> None:
    source, _ = _build_module_with_more_than_cap_bare_calls()
    issues = code_rules_enforcer.check_ignored_must_check_return(
        source,
        PRODUCTION_FILE_PATH,
        None,
        False,
    )
    assert len(issues) == code_rules_enforcer.MAX_IGNORED_MUST_CHECK_RETURN_ISSUES, (
        "The terminal hook path with all_changed_lines=None must cap at the module "
        f"limit, got: {issues!r}"
    )


WRAPPED_CALL_OPEN_PAREN_LINE_NUMBER = 2
WRAPPED_CALL_ARGUMENT_LINE_NUMBER = 3


def test_should_flag_when_changed_line_covers_a_later_line_of_a_wrapped_call() -> None:
    source = (
        "def step() -> None:\n"
        "    find_and_click(\n"
        "        '#submit',\n"
        "    )\n"
    )
    all_changed_lines = {WRAPPED_CALL_ARGUMENT_LINE_NUMBER}
    issues = code_rules_enforcer.check_ignored_must_check_return(
        source,
        PRODUCTION_FILE_PATH,
        all_changed_lines,
        False,
    )
    assert len(issues) == 1, (
        "Editing a later line of a multi-line bare must-check call must still flag it "
        f"because the violation span covers the whole call, got: {issues!r}"
    )
    assert "find_and_click" in issues[0]
