"""Unit tests for code-rules-enforcer boolean naming-pattern check."""

import importlib.util
import pathlib
import sys


_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIRECTORY / "code-rules-enforcer.py",
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
EXPECTED_PREFIX_GUIDANCE = "prefix with is_/has_/should_/can_"


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


def test_should_cap_issues_at_three() -> None:
    source = (
        "def f() -> None:\n"
        "    one = True\n"
        "    two = False\n"
        "    three = True\n"
        "    four = False\n"
        "    five = True\n"
    )
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 3


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
