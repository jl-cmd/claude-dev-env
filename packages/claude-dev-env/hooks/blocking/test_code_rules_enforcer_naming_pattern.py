"""Unit tests for code_rules_enforcer boolean naming-pattern check."""

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
check_boolean_naming = _hook_module.check_boolean_naming
validate_content = _hook_module.validate_content


PRODUCTION_FILE_PATH = "src/app/feature.py"
TEST_FILE_PATH = "src/app/test_feature.py"
CONFIG_FILE_PATH = "src/config/settings.py"
WORKFLOW_FILE_PATH = "src/workflow/orders_tab.py"
HOOK_FILE_PATH = "/home/user/.claude/hooks/blocking/my_hook.py"
EXPECTED_PREFIX_GUIDANCE = "prefix with is_/has_/should_/can_/was_/did_"


def _assert_flags_name(issues: list[str], name: str, line_number: int) -> None:
    expected = f"Line {line_number}: Boolean {name} - {EXPECTED_PREFIX_GUIDANCE}"
    assert expected in issues, f"expected {expected!r} in {issues!r}"


def test_should_flag_boolean_assignment_without_is_prefix() -> None:
    source = "def f() -> None:\n    valid = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_name(issues, "valid", 2)
    assert len(issues) == 1


def test_should_flag_boolean_assignment_without_has_prefix() -> None:
    source = "def f() -> None:\n    permission = False\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_name(issues, "permission", 2)
    assert len(issues) == 1


def test_should_allow_is_prefix() -> None:
    source = "def f() -> None:\n    is_valid = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_has_prefix() -> None:
    source = "def f() -> None:\n    has_permission = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_should_prefix() -> None:
    source = "def f() -> None:\n    should_retry = False\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_can_prefix() -> None:
    source = "def f() -> None:\n    can_edit = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_uppercase_constant_boolean() -> None:
    source = "DEBUG_MODE = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_annotated_boolean_with_valid_prefix() -> None:
    source = "def f() -> None:\n    is_active: bool = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_flag_annotated_boolean_without_prefix() -> None:
    source = "def f() -> None:\n    active: bool = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_name(issues, "active", 2)
    assert len(issues) == 1


def test_should_skip_test_files() -> None:
    source = "def f() -> None:\n    valid = True\n"
    issues = check_boolean_naming(source, TEST_FILE_PATH)
    assert issues == []


def test_should_skip_bare_bool_annotation_without_literal_value() -> None:
    source = "def f() -> None:\n    active: bool\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_skip_annotated_bool_with_non_literal_rhs() -> None:
    source = "def f() -> None:\n    active: bool = compute()\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_flag_tuple_unpacking_of_bool_constants() -> None:
    source = "def f() -> None:\n    valid, permitted = True, False\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_name(issues, "valid", 2)
    _assert_flags_name(issues, "permitted", 2)
    assert len(issues) == 2


def test_should_flag_walrus_boolean_assignment() -> None:
    source = "def f() -> None:\n    if (matched := True):\n        pass\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_name(issues, "matched", 2)
    assert len(issues) == 1


def test_should_allow_class_body_uppercase_constant_boolean() -> None:
    source = "class FeatureFlags:\n    DEBUG_MODE: bool = True\n    TRACING_ENABLED = False\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_skip_hook_infrastructure_files() -> None:
    source = "def f() -> None:\n    valid = True\n"
    issues = check_boolean_naming(source, HOOK_FILE_PATH)
    assert issues == []


def test_should_skip_config_files() -> None:
    source = "class Settings:\n    enabled: bool = True\n"
    issues = check_boolean_naming(source, CONFIG_FILE_PATH)
    assert issues == []


def test_should_skip_workflow_registry_files() -> None:
    source = "def f() -> None:\n    active = True\n"
    issues = check_boolean_naming(source, WORKFLOW_FILE_PATH)
    assert issues == []


def test_should_not_flag_syntax_error_as_issue() -> None:
    source = "def f(:\n    valid = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_validate_content_invokes_boolean_naming_check() -> None:
    source = "def f() -> None:\n    valid = True\n"
    issues = validate_content(source, PRODUCTION_FILE_PATH, old_content="")
    matching_issues = [issue for issue in issues if "Boolean valid" in issue]
    assert matching_issues, (
        f"expected validate_content to surface the boolean-naming issue, got {issues!r}"
    )


def test_should_flag_substring_is_when_not_at_prefix_position() -> None:
    source = "def f() -> None:\n    left_is_upper_snake = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_name(issues, "left_is_upper_snake", 2)
    assert len(issues) == 1, (
        f"'is_' in middle position must not satisfy the prefix rule, got: {issues}"
    )


def test_should_flag_substring_has_when_not_at_prefix_position() -> None:
    source = "def f() -> None:\n    user_has_permission = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_name(issues, "user_has_permission", 2)
    assert len(issues) == 1, (
        f"'has_' in middle position must not satisfy the prefix rule, got: {issues}"
    )


def test_should_flag_substring_should_when_not_at_prefix_position() -> None:
    source = "def f() -> None:\n    user_should_retry = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_name(issues, "user_should_retry", 2)
    assert len(issues) == 1


def test_should_flag_substring_can_when_not_at_prefix_position() -> None:
    source = "def f() -> None:\n    user_can_edit = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_name(issues, "user_can_edit", 2)
    assert len(issues) == 1


def test_should_flag_right_is_literal_substring_match() -> None:
    source = "def f() -> None:\n    right_is_literal = False\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_name(issues, "right_is_literal", 2)
    assert len(issues) == 1, (
        f"PR #232 finding: substring 'is_' in 'right_is_literal' must be flagged, got: {issues}"
    )


def test_should_allow_is_prefix_at_start_when_compound_word_follows() -> None:
    source = "def f() -> None:\n    is_left_upper_snake = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"is_left_upper_snake has prefix at position 0, must pass, got: {issues}"
    )


PARAMETER_PREFIX_GUIDANCE = "prefix with is_/has_/should_/can_/was_/did_"


def _assert_flags_parameter(issues: list[str], name: str, line_number: int) -> None:
    expected = f"Line {line_number}: Boolean parameter {name} - {PARAMETER_PREFIX_GUIDANCE}"
    assert expected in issues, f"expected {expected!r} in {issues!r}"


def test_should_flag_bool_annotated_parameter_without_prefix() -> None:
    source = "def run(dry_run: bool) -> None:\n    print(dry_run)\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_parameter(issues, "dry_run", 1)
    assert len(issues) == 1


def test_should_flag_bool_default_parameter_without_annotation() -> None:
    source = "def run(apply_historical_weight=False) -> None:\n    print(apply_historical_weight)\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_parameter(issues, "apply_historical_weight", 1)
    assert len(issues) == 1


def test_should_flag_keyword_only_bool_parameter_without_prefix() -> None:
    source = "def run(*, click_succeeded: bool = True) -> None:\n    print(click_succeeded)\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_parameter(issues, "click_succeeded", 1)
    assert len(issues) == 1


def test_should_allow_is_prefixed_bool_parameter() -> None:
    source = "def run(is_dry_run: bool) -> None:\n    print(is_dry_run)\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_was_prefixed_bool_parameter() -> None:
    source = "def run(was_clicked: bool = False) -> None:\n    print(was_clicked)\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_did_prefixed_bool_parameter() -> None:
    source = "def run(did_succeed: bool) -> None:\n    print(did_succeed)\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_was_prefixed_bool_assignment() -> None:
    source = "def f() -> None:\n    was_clicked = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_did_prefixed_bool_assignment() -> None:
    source = "def f() -> None:\n    did_run = False\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_skip_single_letter_bool_parameter() -> None:
    source = "def run(x: bool) -> None:\n    print(x)\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_skip_self_parameter_in_method() -> None:
    source = (
        "class Runner:\n"
        "    def run(self, enabled: bool) -> None:\n"
        "        print(self, enabled)\n"
    )
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_parameter(issues, "enabled", 2)
    assert len(issues) == 1


def test_should_not_flag_non_bool_parameter() -> None:
    source = "def run(retries: int) -> None:\n    print(retries)\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_skip_bool_parameter_in_test_file() -> None:
    source = "def run(dry_run: bool) -> None:\n    print(dry_run)\n"
    issues = check_boolean_naming(source, TEST_FILE_PATH)
    assert issues == []


def test_should_pair_positional_defaults_right_aligned() -> None:
    source = (
        "def run(name: str, verbose: bool = False) -> None:\n"
        "    print(name, verbose)\n"
    )
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    _assert_flags_parameter(issues, "verbose", 1)
    assert len(issues) == 1


FULL_MODULE_WITH_TWO_UNPREFIXED_BOOL_PARAMETERS = (
    "def pre_existing(verbose: bool) -> None:\n"
    "    print(verbose)\n"
    "\n\n"
    "def edited(detailed: bool) -> None:\n"
    "    print(detailed)\n"
)
PRE_EXISTING_BOOL_PARAMETER_LINE_NUMBER = 1
EDITED_BOOL_PARAMETER_LINE_NUMBER = 5


def test_should_flag_bool_parameter_on_changed_line() -> None:
    issues = check_boolean_naming(
        FULL_MODULE_WITH_TWO_UNPREFIXED_BOOL_PARAMETERS,
        PRODUCTION_FILE_PATH,
        {EDITED_BOOL_PARAMETER_LINE_NUMBER},
        False,
    )
    _assert_flags_parameter(issues, "detailed", EDITED_BOOL_PARAMETER_LINE_NUMBER)
    assert len(issues) == 1, (
        "Only the bool parameter on the changed line must be flagged, got: "
        f"{issues!r}"
    )


def test_should_not_flag_pre_existing_bool_parameter_on_unchanged_line() -> None:
    issues = check_boolean_naming(
        FULL_MODULE_WITH_TWO_UNPREFIXED_BOOL_PARAMETERS,
        PRODUCTION_FILE_PATH,
        {EDITED_BOOL_PARAMETER_LINE_NUMBER},
        False,
    )
    assert not any("verbose" in each_issue for each_issue in issues), (
        "A pre-existing unprefixed bool parameter on an unedited line must not block "
        f"the edit, got: {issues!r}"
    )
