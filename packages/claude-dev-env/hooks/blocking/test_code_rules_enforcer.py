"""Tests covering file-global constant reference resolution edge cases.

Loop2-C: class-decorator usage of a module-level constant must count as a
caller so the single-caller rule fires correctly.

Loop2-D: module-scope usages must register as a distinct caller bucket so
the "zero function references" exemption does not swallow real references.

Loop1-1: scope-bounded assertion collection — nested function/class bodies
inside compound statements must not have their assertions attributed to the
enclosing test function.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import sys
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

_BLOCKING_DIR = Path(__file__).resolve().parent
_HOOKS_TREE_DIR = _BLOCKING_DIR.parent
if str(_BLOCKING_DIR) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIR))
if str(_HOOKS_TREE_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_TREE_DIR))

from code_rules_path_utils import is_config_file as path_utils_is_config_file  # noqa: E402
from hooks_constants.banned_identifiers_constants import (  # noqa: E402
    ALL_BANNED_IDENTIFIERS as config_all_banned_identifiers,
    BANNED_IDENTIFIER_MESSAGE_SUFFIX as config_banned_identifier_message_suffix,
    BANNED_IDENTIFIER_SKIP_ADVISORY as config_banned_identifier_skip_advisory,
    MAX_BANNED_IDENTIFIER_ISSUES as config_max_banned_identifier_issues,
)
from hooks_constants.hardcoded_user_path_constants import (  # noqa: E402
    HARDCODED_USER_PATH_GUIDANCE as config_hardcoded_user_path_guidance,
    HARDCODED_USER_PATH_PATTERN as config_hardcoded_user_path_pattern,
    MAX_HARDCODED_USER_PATH_ISSUES as config_max_hardcoded_user_path_issues,
)
from hooks_constants.stuttering_check_config import (  # noqa: E402
    MAX_STUTTERING_PREFIX_ISSUES as config_max_stuttering_prefix_issues,
    STUTTERING_ALL_PREFIX_PATTERN as config_stuttering_all_prefix_pattern,
)

PRODUCTION_FILE_PATH = "packages/claude-dev-env/hooks/blocking/example_production.py"


def test_should_treat_repo_relative_hook_path_as_hook_infrastructure() -> None:
    relative_hook_path = "packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py"
    assert code_rules_enforcer.is_hook_infrastructure(relative_hook_path) is True


def test_should_treat_backslash_repo_relative_hook_path_as_hook_infrastructure() -> None:
    relative_hook_path = "packages\\claude-dev-env\\hooks\\blocking\\code_rules_enforcer.py"
    assert code_rules_enforcer.is_hook_infrastructure(relative_hook_path) is True


def test_should_not_treat_unrelated_repo_relative_path_as_hook_infrastructure() -> None:
    relative_source_path = "packages/claude-dev-env/skills/bugteam/scripts/runner.py"
    assert code_rules_enforcer.is_hook_infrastructure(relative_source_path) is False


def test_should_exempt_repo_relative_hook_file_from_function_length() -> None:
    body_lines = "\n".join(f"    bound_{each_index} = {each_index}" for each_index in range(70))
    grown_function_source = "def grown_function() -> None:\n" + body_lines + "\n"
    relative_hook_path = "packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py"
    assert code_rules_enforcer.check_function_length(grown_function_source, relative_hook_path) == []


def test_should_expose_all_banned_identifiers_from_config() -> None:
    expected_banned_identifiers = frozenset({
        "result", "data", "output", "response", "value", "item", "temp",
        "argv", "args", "kwargs", "argc",
    })
    actual_banned_identifiers = getattr(
        code_rules_enforcer, "ALL_BANNED_IDENTIFIERS", None
    )
    assert actual_banned_identifiers is not None, (
        "Renamed constant ALL_BANNED_IDENTIFIERS must be importable from "
        "config/banned_identifiers_constants.py and re-exposed on the "
        f"enforcer module, got: {actual_banned_identifiers!r}"
    )
    assert expected_banned_identifiers <= actual_banned_identifiers, (
        "ALL_BANNED_IDENTIFIERS must contain every expected banned identifier; "
        f"missing: {expected_banned_identifiers - actual_banned_identifiers!r}"
    )


def test_should_source_banned_identifier_companion_constants_from_config() -> None:
    assert (
        code_rules_enforcer.MAX_BANNED_IDENTIFIER_ISSUES
        is config_max_banned_identifier_issues
    )
    assert (
        code_rules_enforcer.BANNED_IDENTIFIER_MESSAGE_SUFFIX
        is config_banned_identifier_message_suffix
    )
    assert (
        code_rules_enforcer.BANNED_IDENTIFIER_SKIP_ADVISORY
        is config_banned_identifier_skip_advisory
    )


def test_should_reexport_hardcoded_user_path_pattern_from_config() -> None:
    assert code_rules_enforcer.HARDCODED_USER_PATH_PATTERN is config_hardcoded_user_path_pattern


def test_should_reexport_max_hardcoded_user_path_issues_from_config() -> None:
    assert code_rules_enforcer.MAX_HARDCODED_USER_PATH_ISSUES == config_max_hardcoded_user_path_issues


def test_should_reexport_hardcoded_user_path_guidance_from_config() -> None:
    assert code_rules_enforcer.HARDCODED_USER_PATH_GUIDANCE == config_hardcoded_user_path_guidance


def test_should_reexport_all_banned_identifiers_from_config() -> None:
    assert code_rules_enforcer.ALL_BANNED_IDENTIFIERS is config_all_banned_identifiers


def test_should_flag_constant_used_only_in_class_level_decorator() -> None:
    source = (
        "TIMEOUT = 5\n"
        "\n"
        "def register(value):\n"
        "    def wrap(cls):\n"
        "        return cls\n"
        "    return wrap\n"
        "\n"
        "@register(TIMEOUT)\n"
        "class Foo:\n"
        "    pass\n"
    )
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert any(
        "TIMEOUT" in issue and "only 1 function/method" in issue for issue in issues
    ), f"Expected class-decorator usage to register as a caller, got: {issues}"


def test_should_flag_constant_used_once_at_module_scope_and_once_in_function() -> None:
    source = "UPPER = 1\nSHADOW = UPPER\n\ndef lonely_caller():\n    return UPPER\n"
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Expected module-scope + function usage to count as 2 distinct callers, got: {issues}"
    )


UNUSED_OPTIONAL_PRODUCTION_FILE_PATH = "packages/app/services/feature.py"
UNUSED_OPTIONAL_TEST_FILE_PATH = "packages/app/tests/test_feature.py"
UNUSED_OPTIONAL_CONFIG_FILE_PATH = "packages/app/config/constants.py"


def test_should_flag_optional_param_never_varied_in_file() -> None:
    source = (
        "def build_url(path: str, prefix: str = '/api') -> str:\n"
        "    return f'{prefix}{path}'\n"
        "\n"
        "def call_first() -> str:\n"
        "    return build_url('/users')\n"
        "\n"
        "def call_second() -> str:\n"
        "    return build_url('/items')\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_PRODUCTION_FILE_PATH
    )
    assert any("prefix" in issue for issue in issues), (
        f"Expected 'prefix' flagged as never-varied, got: {issues}"
    )


def test_should_not_flag_when_param_is_varied_at_call_site() -> None:
    source = (
        "def build_url(path: str, prefix: str = '/api') -> str:\n"
        "    return f'{prefix}{path}'\n"
        "\n"
        "def call_with_default() -> str:\n"
        "    return build_url('/users')\n"
        "\n"
        "def call_with_override() -> str:\n"
        "    return build_url('/items', prefix='/v2')\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_PRODUCTION_FILE_PATH
    )
    assert not any("prefix" in issue for issue in issues), (
        f"Expected 'prefix' not flagged when varied, got: {issues}"
    )


def test_should_not_flag_unused_optional_in_test_files() -> None:
    source = (
        "def build_url(path: str, prefix: str = '/api') -> str:\n"
        "    return f'{prefix}{path}'\n"
        "\n"
        "def call_first() -> str:\n"
        "    return build_url('/users')\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_TEST_FILE_PATH
    )
    assert issues == [], f"Expected no issues in test file, got: {issues}"


def test_should_not_flag_unused_optional_in_config_files() -> None:
    source = (
        "def build_url(path: str, prefix: str = '/api') -> str:\n"
        "    return f'{prefix}{path}'\n"
        "\n"
        "def call_first() -> str:\n"
        "    return build_url('/users')\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_CONFIG_FILE_PATH
    )
    assert issues == [], f"Expected no issues in config file, got: {issues}"


def test_should_not_flag_when_no_same_file_call_sites_exist() -> None:
    source = (
        "def build_url(path: str, prefix: str = '/api') -> str:\n"
        "    return f'{prefix}{path}'\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Expected no issues when no same-file call sites, got: {issues}"
    )


def test_should_include_line_number_and_param_name_in_issue() -> None:
    source = (
        "def fetch(url: str, timeout: int = 30) -> str:\n"
        "    return get(url, timeout=timeout)\n"
        "\n"
        "def run_fetch() -> str:\n"
        "    return fetch('http://example.com')\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_PRODUCTION_FILE_PATH
    )
    assert any("Line 1" in issue and "timeout" in issue for issue in issues), (
        f"Expected issue with line number and param name, got: {issues}"
    )


def test_should_flag_when_every_call_passes_the_exact_default() -> None:
    source = (
        "def fetch(url: str, timeout: int = 30) -> str:\n"
        "    return get(url, timeout=timeout)\n"
        "\n"
        "def run_fetch() -> str:\n"
        "    return fetch('http://example.com', timeout=30)\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_PRODUCTION_FILE_PATH
    )
    assert any("timeout" in issue for issue in issues), (
        f"Expected 'timeout' flagged when every call passes the exact default, got: {issues}"
    )


INCOMPLETE_MOCK_TEST_FILE_PATH = "packages/app/tests/test_orders.py"
INCOMPLETE_MOCK_PRODUCTION_FILE_PATH = "packages/app/services/orders.py"


def test_should_advise_when_mock_missing_accessed_field(capsys: object) -> None:
    source = (
        "mock_order = {'id': 1}\n"
        "\n"
        "def test_order_total() -> None:\n"
        "    total = mock_order['total']\n"
        "    assert total > 0\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" in captured.err and "total" in captured.err, (
        f"Expected advisory about missing 'total' field, got: {captured.err!r}"
    )


def test_should_not_advise_when_mock_has_all_accessed_fields(capsys: object) -> None:
    source = (
        "mock_order = {'id': 1, 'total': 50}\n"
        "\n"
        "def test_order_total() -> None:\n"
        "    total = mock_order['total']\n"
        "    assert total > 0\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" not in captured.err, (
        f"Expected no advisory when all fields present, got: {captured.err!r}"
    )


def test_should_not_advise_for_incomplete_mocks_in_production_files(capsys: object) -> None:
    source = (
        "mock_order = {'id': 1}\n"
        "\n"
        "def run_order() -> None:\n"
        "    total = mock_order['total']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_PRODUCTION_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" not in captured.err, (
        f"Expected no advisory in production file, got: {captured.err!r}"
    )


def test_should_advise_for_attribute_access_on_mock_object(capsys: object) -> None:
    source = (
        "class MockUser:\n"
        "    pass\n"
        "\n"
        "mock_user = MockUser()\n"
        "mock_user.name = 'Alice'\n"
        "\n"
        "def test_user_email() -> None:\n"
        "    email = mock_user.email\n"
        "    assert email\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_user" in captured.err and "email" in captured.err, (
        f"Expected advisory about missing 'email' attribute, got: {captured.err!r}"
    )


DUPLICATED_FORMAT_PRODUCTION_FILE_PATH = "packages/app/services/api_client.py"
DUPLICATED_FORMAT_TEST_FILE_PATH = "packages/app/tests/test_api_client.py"


def test_should_advise_when_fstring_skeleton_appears_three_or_more_times(capsys: object) -> None:
    source = (
        "def get_user(user_id: str) -> str:\n"
        "    return f'/api/{user_id}'\n"
        "\n"
        "def get_order(order_id: str) -> str:\n"
        "    return f'/api/{order_id}'\n"
        "\n"
        "def get_product(product_id: str) -> str:\n"
        "    return f'/api/{product_id}'\n"
    )
    code_rules_enforcer.check_duplicated_format_patterns(
        source, DUPLICATED_FORMAT_PRODUCTION_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/api/" in captured.err and "3" in captured.err, (
        f"Expected advisory for repeated /api/<x> pattern, got: {captured.err!r}"
    )


def test_should_not_advise_when_fstring_skeleton_appears_fewer_than_three_times(capsys: object) -> None:
    source = (
        "def get_user(user_id: str) -> str:\n"
        "    return f'/api/{user_id}'\n"
        "\n"
        "def get_order(order_id: str) -> str:\n"
        "    return f'/api/{order_id}'\n"
    )
    code_rules_enforcer.check_duplicated_format_patterns(
        source, DUPLICATED_FORMAT_PRODUCTION_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/api/" not in captured.err, (
        f"Expected no advisory for pattern appearing only twice, got: {captured.err!r}"
    )


def test_should_not_advise_for_duplicated_format_patterns_in_test_files(capsys: object) -> None:
    source = (
        "def test_user() -> None:\n"
        "    url_a = f'/api/{1}'\n"
        "    url_b = f'/api/{2}'\n"
        "    url_c = f'/api/{3}'\n"
    )
    code_rules_enforcer.check_duplicated_format_patterns(
        source, DUPLICATED_FORMAT_TEST_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/api/" not in captured.err, (
        f"Expected no advisory in test file, got: {captured.err!r}"
    )


def test_should_advise_with_distinct_skeletons(capsys: object) -> None:
    source = (
        "def first(team: str, user: str) -> str:\n"
        "    return f'/teams/{team}/users/{user}'\n"
        "\n"
        "def second(team: str, role: str) -> str:\n"
        "    return f'/teams/{team}/users/{role}'\n"
        "\n"
        "def third(team: str, admin: str) -> str:\n"
        "    return f'/teams/{team}/users/{admin}'\n"
    )
    code_rules_enforcer.check_duplicated_format_patterns(
        source, DUPLICATED_FORMAT_PRODUCTION_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/teams/" in captured.err, (
        f"Expected advisory for repeated /teams/<x>/users/<x> pattern, got: {captured.err!r}"
    )


def test_build_fstring_skeleton_preserves_literal_interp_substring() -> None:
    joined_str_expression = ast.parse("f'PREFIX INTERP {value} SUFFIX'", mode="eval").body
    assert isinstance(joined_str_expression, ast.JoinedStr)
    skeleton = code_rules_enforcer._build_fstring_skeleton(joined_str_expression)
    assert skeleton == "PREFIX INTERP <x> SUFFIX", (
        "Literal 'INTERP' text inside an f-string must survive skeleton building — "
        f"only interpolation slots should become '<x>'. Got: {skeleton!r}"
    )


CONSTANT_EQUALITY_TEST_FILE_PATH = "packages/app/tests/test_constants.py"


def test_should_not_flag_two_named_constants_compared_to_each_other() -> None:
    source = (
        "FOO = 'a'\n"
        "BAR = 'b'\n"
        "\n"
        "def test_constants_differ() -> None:\n"
        "    assert FOO == BAR\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(
        source, CONSTANT_EQUALITY_TEST_FILE_PATH
    )
    assert issues == [], (
        f"Expected no flag when both sides are named constants, got: {issues}"
    )


def test_should_flag_named_constant_compared_to_literal() -> None:
    source = (
        "FOO = 'a'\n"
        "\n"
        "def test_foo_value() -> None:\n"
        "    assert FOO == 'literal'\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(
        source, CONSTANT_EQUALITY_TEST_FILE_PATH
    )
    assert any("constant-value test" in issue for issue in issues), (
        f"Expected flag when UPPER_SNAKE compared to literal, got: {issues}"
    )


NESTED_FUNCTION_PRODUCTION_FILE_PATH = "packages/app/services/nested.py"


def test_should_not_flag_nested_function_optional_param() -> None:
    source = (
        "def outer() -> None:\n"
        "    def inner(timeout: int = 30) -> None:\n"
        "        pass\n"
        "    inner()\n"
        "    inner()\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, NESTED_FUNCTION_PRODUCTION_FILE_PATH
    )
    assert not any("timeout" in issue for issue in issues), (
        f"Expected nested function 'timeout' not flagged, got: {issues}"
    )


def test_should_advise_when_mock_defined_inside_test_function_is_incomplete(
    capsys: object,
) -> None:
    source = (
        "def test_thing() -> None:\n"
        "    mock_user = {'name': 'x'}\n"
        "    assert mock_user['email'] == 'y'\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_user" in captured.err and "email" in captured.err, (
        f"Expected advisory for mock defined inside test function, got: {captured.err!r}"
    )


def test_should_emit_advisories_for_incomplete_mocks_and_format_patterns_via_validate_content(
    capsys: object,
) -> None:
    incomplete_mock_source = (
        "mock_order = {'id': 1}\n"
        "\n"
        "def test_order_total() -> None:\n"
        "    total = mock_order['total']\n"
        "    assert total > 0\n"
    )
    code_rules_enforcer.validate_content(
        incomplete_mock_source, INCOMPLETE_MOCK_TEST_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" in captured.err and "total" in captured.err, (
        f"Expected incomplete-mock advisory from validate_content, got: {captured.err!r}"
    )

    repeated_pattern_source = (
        "def get_user(user_id: str) -> str:\n"
        "    return f'/api/{user_id}'\n"
        "\n"
        "def get_order(order_id: str) -> str:\n"
        "    return f'/api/{order_id}'\n"
        "\n"
        "def get_product(product_id: str) -> str:\n"
        "    return f'/api/{product_id}'\n"
    )
    code_rules_enforcer.validate_content(
        repeated_pattern_source, DUPLICATED_FORMAT_PRODUCTION_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/api/" in captured.err and "3" in captured.err, (
        f"Expected duplicated-format advisory from validate_content, got: {captured.err!r}"
    )


SCOPE_KEYED_MOCK_TEST_FILE_PATH = "packages/app/tests/test_scope_mocks.py"
KWARGS_EXPANSION_PRODUCTION_FILE_PATH = "packages/app/services/fetcher.py"


def test_should_check_each_scope_mock_against_its_own_field_set(capsys: object) -> None:
    """Same mock_user name in two test functions with different field sets.

    First function defines mock_user with only 'id'; accesses 'email' — should warn.
    Second function defines mock_user with 'id' and 'email'; accesses 'email' — no warn.
    The second definition must NOT overwrite the first scope's tracking.
    """
    source = (
        "def test_first_scope() -> None:\n"
        "    mock_user = {'id': 1}\n"
        "    email = mock_user['email']\n"
        "\n"
        "def test_second_scope() -> None:\n"
        "    mock_user = {'id': 2, 'email': 'b@b.com'}\n"
        "    email = mock_user['email']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, SCOPE_KEYED_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    advisory_lines = [
        line for line in captured.err.splitlines() if "mock_user" in line and "email" in line
    ]
    assert len(advisory_lines) == 1, (
        f"Expected exactly 1 advisory (first scope missing email), got: {captured.err!r}"
    )


def test_should_emit_exactly_one_advisory_for_repeated_accesses_to_same_missing_field(
    capsys: object,
) -> None:
    """mock_user accessed 5 times for 'email' but email is missing — emit exactly one advisory."""
    source = (
        "def test_repeated_access() -> None:\n"
        "    mock_user = {'id': 1}\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, SCOPE_KEYED_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    advisory_lines = [
        line for line in captured.err.splitlines() if "mock_user" in line and "email" in line
    ]
    assert len(advisory_lines) == 1, (
        f"Expected exactly 1 advisory for 5 repeated accesses to missing 'email', got: {captured.err!r}"
    )


def test_should_not_flag_optional_param_when_only_call_site_uses_kwargs_expansion() -> None:
    """A call using **defaults passes unknown values — the param must NOT be flagged."""
    source = (
        "def fetch(url: str, timeout: int = 30) -> str:\n"
        "    return url\n"
        "\n"
        "def run() -> str:\n"
        "    defaults = {'timeout': 30}\n"
        "    return fetch('http://example.com', **defaults)\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, KWARGS_EXPANSION_PRODUCTION_FILE_PATH
    )
    assert not any("timeout" in issue for issue in issues), (
        f"Expected 'timeout' NOT flagged when call uses **kwargs expansion, got: {issues}"
    )


MODULE_LEVEL_MOCK_TEST_FILE_PATH = "packages/app/tests/test_module_level.py"


def test_should_emit_exactly_one_advisory_for_module_level_mock_with_missing_field(
    capsys: object,
) -> None:
    """Module-level mock_user with one missing field access should produce ONE advisory.

    Finding 4: ast.walk() already yields the root Module node, so
    [module_tree, *ast.walk(module_tree)] iterates the module twice and
    previously produced two identical advisories for module-level mocks.
    """
    source = (
        "mock_user = {'name': 'Alice'}\n"
        "\n"
        "def test_email_present() -> None:\n"
        "    email = mock_user['email']\n"
        "    assert email\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    advisory_lines = [
        line for line in captured.err.splitlines() if "mock_user" in line and "email" in line
    ]
    assert len(advisory_lines) == 1, (
        f"Expected exactly 1 advisory for module-level mock missing 'email', got: {captured.err!r}"
    )


def test_is_config_file_rejects_filename_only_config_pattern() -> None:
    """Paths where 'config' appears only in the filename (not as a directory segment) must return False."""
    assert code_rules_enforcer.is_config_file("scripts/db/config.py") is False, (
        "scripts/db/config.py — filename is config.py but parent dir is db, must be False"
    )
    assert code_rules_enforcer.is_config_file("lib/myconfig.py") is False, (
        "lib/myconfig.py — config appears only in the filename stem, must be False"
    )
    assert code_rules_enforcer.is_config_file("src/app_config.py") is False, (
        "src/app_config.py — config appears only in the filename stem, must be False"
    )


def test_is_config_file_via_path_utils_returns_same_results_as_enforcer() -> None:
    """is_config_file from code_rules_path_utils must agree with the enforcer on all sample paths."""
    all_sample_paths = [
        "scripts/db/config.py",
        "config/timing.py",
        "settings.py",
    ]
    for each_path in all_sample_paths:
        enforcer_result = code_rules_enforcer.is_config_file(each_path)
        path_utils_result = path_utils_is_config_file(each_path)
        assert enforcer_result == path_utils_result, (
            f"is_config_file diverged for {each_path!r}: "
            f"enforcer={enforcer_result}, code_rules_path_utils={path_utils_result}"
        )


def test_is_exempt_for_advisory_scan_returns_true_for_config_file() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("project/config/constants.py") is True


def test_is_exempt_for_advisory_scan_returns_true_for_test_file() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("test_example.py") is True


def test_is_exempt_for_advisory_scan_returns_true_for_workflow_registry() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("app/workflow/states.py") is True


def test_is_exempt_for_advisory_scan_returns_true_for_migration() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("app/migrations/0001_initial.py") is True


def test_is_exempt_for_advisory_scan_returns_false_for_production_file() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("packages/myapp/some_module.py") is False


def test_scan_function_body_constants_finds_upper_snake_in_function() -> None:
    source = (
        "def fetch():\n"
        "    MAX_RETRIES = 3\n"
        "    for attempt in range(MAX_RETRIES):\n"
        "        pass\n"
    )
    advisory_issues = code_rules_enforcer._scan_function_body_constants(source)
    assert any("MAX_RETRIES" in issue for issue in advisory_issues)


def test_scan_function_body_constants_does_not_flag_module_level() -> None:
    source = "MAX_RETRIES = 3\n\ndef fetch():\n    pass\n"
    advisory_issues = code_rules_enforcer._scan_function_body_constants(source)
    assert advisory_issues == []


def test_advisory_should_not_flag_class_attribute_after_method_def() -> None:
    source_with_class_attribute_after_method = (
        "class ExampleModel:\n"
        "    def method_a(self) -> None:\n"
        "        pass\n"
        "\n"
        "    TABLE_NAME = \"example\"\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source_with_class_attribute_after_method,
        "example_module.py",
    )
    assert advisory_issues == [], (
        "Class-level TABLE_NAME attribute must not be flagged as function-local"
    )


def test_advisory_should_still_flag_actual_method_body_constant() -> None:
    source_with_method_body_constant = (
        "class ExampleModel:\n"
        "    def method_a(self) -> None:\n"
        "        MAXIMUM_RETRIES = 3\n"
        "        return None\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source_with_method_body_constant,
        "example_module.py",
    )
    assert len(advisory_issues) == 1, (
        "Method-body UPPER_SNAKE constant must still surface as advisory"
    )
    assert "MAXIMUM_RETRIES" in advisory_issues[0]


def test_advisory_should_flag_annotated_function_body_constant() -> None:
    source_with_annotated_function_body_constant = (
        "def example_function() -> None:\n"
        "    MAXIMUM_RETRIES: int = 3\n"
        "    return None\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source_with_annotated_function_body_constant,
        "example_module.py",
    )
    assert len(advisory_issues) == 1, (
        "Annotated function-body UPPER_SNAKE constant (PEP 526) must surface as advisory"
    )
    assert "MAXIMUM_RETRIES" in advisory_issues[0]


def test_advisory_should_flag_outer_constants_after_nested_def() -> None:
    source_with_nested_def = (
        "def outer():\n"
        "    OUTER_CONST = 1\n"
        "    def inner():\n"
        "        INNER_CONST = 2\n"
        "    ANOTHER_OUTER = 3\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source_with_nested_def,
        "example_module.py",
    )
    flagged_names = " ".join(advisory_issues)
    assert "OUTER_CONST" in flagged_names, (
        "OUTER_CONST before nested def must be flagged"
    )
    assert "INNER_CONST" in flagged_names, (
        "INNER_CONST inside nested def must be flagged"
    )
    assert "ANOTHER_OUTER" in flagged_names, (
        "ANOTHER_OUTER after nested def must be flagged — this is the regression case"
    )


def test_should_not_leak_shadowed_nested_assignment_into_outer_mock_known_fields(
    capsys: object,
) -> None:
    """Assignment collector must skip nested scopes that shadow the mock name.

    The access collector uses _walk_scope_skipping_shadowed; the assignment
    collector must do the same, otherwise attribute assignments inside a
    nested function that redefines mock_user leak into the outer mock's
    known-fields set and suppress advisories for genuinely missing fields.
    """
    source = (
        "mock_user = {'id': 1}\n"
        "outer_value = mock_user['email']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    mock_user = {'id': 2}\n"
        "    mock_user.email = 'shadowed@example.com'\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    advisory_lines = [
        line for line in captured.err.splitlines() if "mock_user" in line and "email" in line
    ]
    assert len(advisory_lines) == 1, (
        "Expected outer mock's missing 'email' advisory to fire even when a shadowing "
        f"nested function assigns mock_user.email, got: {captured.err!r}"
    )


def test_should_treat_annotated_assignment_as_shadowing_in_nested_scope(
    capsys: object,
) -> None:
    """AnnAssign must shadow just like Assign.

    When a nested scope re-binds the mock variable via an annotated
    assignment (``mock_user: dict = {...}``), accesses inside that nested
    scope belong to the inner mock, not the outer one. If the shadow
    detector ignores AnnAssign, inner accesses leak out and cause
    spurious advisories against the outer mock for fields it never sees.
    """
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    mock_user: dict = {'id': 2, 'timezone': 'UTC'}\n"
        "    inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    leaked_advisories = [
        line
        for line in captured.err.splitlines()
        if "mock_user" in line and "timezone" in line
    ]
    assert leaked_advisories == [], (
        "Expected no advisory on the outer mock for 'timezone' — that field is "
        "accessed only inside a nested scope that re-binds mock_user via an "
        f"annotated assignment, got: {captured.err!r}"
    )


def _assert_inner_field_did_not_leak(
    captured_stderr: str,
    inner_only_field_name: str,
    binding_form_description: str,
) -> None:
    leaked_advisories = [
        line
        for line in captured_stderr.splitlines()
        if "mock_user" in line and inner_only_field_name in line
    ]
    assert leaked_advisories == [], (
        f"Expected no advisory on the outer mock for {inner_only_field_name!r} — "
        f"that field is accessed only inside a nested scope that re-binds "
        f"mock_user via {binding_form_description}, got: {captured_stderr!r}"
    )


def test_should_treat_assignment_inside_if_block_as_shadowing(capsys: object) -> None:
    """Binding inside an ``if`` block must shadow the outer mock name.

    Python binds a name locally when it is assigned *anywhere* in the
    function body, including inside a branch. A shadow detector that only
    inspects the top-level statements misses this form.
    """
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    if True:\n"
        "        mock_user = {'id': 2, 'timezone': 'UTC'}\n"
        "    inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "an assignment nested inside an if-block"
    )


def test_should_treat_for_loop_target_as_shadowing(capsys: object) -> None:
    """A ``for`` loop target binds the name locally and must shadow."""
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    for mock_user in [{'id': 2, 'timezone': 'UTC'}]:\n"
        "        inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "a for-loop target"
    )


def test_should_treat_try_except_handler_name_as_shadowing(capsys: object) -> None:
    """An ``except ... as mock_user`` handler binds the name locally."""
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    try:\n"
        "        raise ValueError({'id': 2, 'timezone': 'UTC'})\n"
        "    except ValueError as mock_user:\n"
        "        inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "an except-handler binding"
    )


def test_should_treat_walrus_expression_as_shadowing(capsys: object) -> None:
    """A named-expression walrus binding inside a condition must shadow."""
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    if (mock_user := {'id': 2, 'timezone': 'UTC'}):\n"
        "        inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "a walrus named-expression"
    )


def test_should_treat_function_parameter_as_shadowing(capsys: object) -> None:
    """A parameter named like the mock variable must shadow the outer binding."""
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner(mock_user: dict) -> None:\n"
        "    inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "a function parameter of the same name"
    )


def test_should_treat_import_asname_as_shadowing(capsys: object) -> None:
    """An ``import ... as mock_user`` must shadow the outer mock name."""
    source = (
        "mock_user = {'id': 1, 'name': 'outer'}\n"
        "outer_value = mock_user['name']\n"
        "\n"
        "def test_inner() -> None:\n"
        "    import collections as mock_user\n"
        "    inner_value = mock_user['timezone']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    _assert_inner_field_did_not_leak(
        captured.err, "timezone", "an import-asname binding"
    )


def test_should_not_advise_when_duplicated_fstring_literal_is_short(capsys: object) -> None:
    """Short logger-prefix style f-strings must not emit a duplication advisory.

    A three-times-repeated ``f"Got {x}"`` has only four characters of literal
    text (``"Got "``). Flagging such short fragments creates noise for common
    logging prefixes. The heuristic requires a minimum amount of structural
    literal text before an advisory fires.
    """
    source = (
        "def first(value: str) -> str:\n"
        "    return f'Got {value}'\n"
        "\n"
        "def second(value: str) -> str:\n"
        "    return f'Got {value}'\n"
        "\n"
        "def third(value: str) -> str:\n"
        "    return f'Got {value}'\n"
    )
    code_rules_enforcer.check_duplicated_format_patterns(
        source, DUPLICATED_FORMAT_PRODUCTION_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "Got" not in captured.err, (
        "Expected no advisory for a short repeated f-string literal fragment, "
        f"got: {captured.err!r}"
    )


def test_should_still_advise_when_duplicated_fstring_literal_is_long(capsys: object) -> None:
    """Longer duplicated f-string skeletons must continue to fire.

    The short-literal heuristic must not regress the existing
    ``/api/<x>`` and ``/teams/<x>/users/<x>`` advisories — those path
    skeletons carry enough structural literal text to warrant a helper.
    """
    source = (
        "def get_user(user_id: str) -> str:\n"
        "    return f'/api/{user_id}'\n"
        "\n"
        "def get_order(order_id: str) -> str:\n"
        "    return f'/api/{order_id}'\n"
        "\n"
        "def get_product(product_id: str) -> str:\n"
        "    return f'/api/{product_id}'\n"
    )
    code_rules_enforcer.check_duplicated_format_patterns(
        source, DUPLICATED_FORMAT_PRODUCTION_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/api/" in captured.err, (
        "Expected the existing /api/<x> path-shape advisory to still fire, "
        f"got: {captured.err!r}"
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


INLINE_LITERAL_PRODUCTION_FILE_PATH = "packages/app/services/inline_literal.py"


def test_check_inline_literal_collections_flags_three_string_set_in_function() -> None:
    source = (
        "def is_known(value: str) -> bool:\n"
        "    return value in {'true', 'false', 'none'}\n"
    )
    issues = code_rules_enforcer.check_inline_literal_collections(
        source, INLINE_LITERAL_PRODUCTION_FILE_PATH
    )
    assert len(issues) == 1, f"Expected 3-element string set flagged, got: {issues}"


STRING_MAGIC_PRODUCTION_FILE_PATH = "packages/app/services/string_magic.py"


def test_check_string_literal_magic_flags_env_var_name() -> None:
    source = (
        "import os\n"
        "\n"
        "def fetch_secret() -> str:\n"
        "    return os.environ['STRIPE_SECRET']\n"
    )
    issues = code_rules_enforcer.check_string_literal_magic(
        source, STRING_MAGIC_PRODUCTION_FILE_PATH
    )
    assert any("STRIPE_SECRET" in each_issue for each_issue in issues), (
        f"Expected env-var name flagged, got: {issues}"
    )


CONSTANTS_OUTSIDE_CONFIG_PRODUCTION_FILE_PATH = "packages/app/services/encoding.py"


def test_check_constants_outside_config_flags_annotated_assignment() -> None:
    source = "TEXT_FILE_ENCODING: str = 'utf-8'\n"
    issues = code_rules_enforcer.check_constants_outside_config(
        source, CONSTANTS_OUTSIDE_CONFIG_PRODUCTION_FILE_PATH
    )
    assert any("TEXT_FILE_ENCODING" in each_issue for each_issue in issues), (
        f"Expected annotated UPPER_SNAKE assignment flagged, got: {issues}"
    )


def test_check_constants_outside_config_reports_more_than_three_constants() -> None:
    source = (
        "ALPHA_VALUE = 1\n"
        "BETA_VALUE = 2\n"
        "GAMMA_VALUE = 3\n"
        "DELTA_VALUE = 4\n"
        "EPSILON_VALUE = 5\n"
        "\n"
        "def consumer() -> int:\n"
        "    return ALPHA_VALUE + BETA_VALUE\n"
    )
    issues = code_rules_enforcer.check_constants_outside_config(
        source, CONSTANTS_OUTSIDE_CONFIG_PRODUCTION_FILE_PATH
    )
    expected_constant_count = 5
    assert len(issues) == expected_constant_count, (
        f"Expected all {expected_constant_count} constants reported, got {len(issues)}: {issues}"
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


SYS_PATH_INSERT_PRODUCTION_FILE_PATH = "packages/app/services/loader.py"
SYS_PATH_INSERT_HOOK_INFRASTRUCTURE_FILE_PATH = "/repo/.claude/hooks/blocking/some_hook.py"


def test_sys_path_insert_should_flag_mismatched_guard_path() -> None:
    source = (
        "import sys\n"
        'if "wrong_path" not in sys.path:\n'
        '    sys.path.insert(0, "actual_path")\n'
    )
    issues = code_rules_enforcer.check_sys_path_insert_deduplication_guard(
        source, SYS_PATH_INSERT_PRODUCTION_FILE_PATH
    )
    assert any("sys.path.insert" in each_issue for each_issue in issues), (
        "Guard testing a different value than what is inserted must be flagged, "
        f"got: {issues}"
    )


def test_sys_path_insert_should_not_flag_matching_guard_path() -> None:
    source = (
        "import sys\n"
        'if "correct_path" not in sys.path:\n'
        '    sys.path.insert(0, "correct_path")\n'
    )
    issues = code_rules_enforcer.check_sys_path_insert_deduplication_guard(
        source, SYS_PATH_INSERT_PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Guard testing the same value that is inserted must not be flagged, got: {issues}"
    )


def test_sys_path_insert_should_not_flag_guarded_insert_in_class_body() -> None:
    source = (
        "import sys\n"
        "class Configurator:\n"
        "    target = '/some/path'\n"
        "    if target not in sys.path:\n"
        "        sys.path.insert(0, target)\n"
    )
    issues = code_rules_enforcer.check_sys_path_insert_deduplication_guard(
        source, SYS_PATH_INSERT_PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Guarded sys.path.insert directly in a class body must not be flagged, got: {issues}"
    )


def test_sys_path_insert_should_skip_hook_infrastructure_files() -> None:
    source = "import sys\nsys.path.insert(0, '/some/path')\n"
    issues = code_rules_enforcer.check_sys_path_insert_deduplication_guard(
        source, SYS_PATH_INSERT_HOOK_INFRASTRUCTURE_FILE_PATH
    )
    assert issues == [], (
        f"Hook infrastructure files are exempt from this rule, got: {issues}"
    )


def test_validate_content_honors_empty_full_file_content_for_thin_wrapper_check() -> None:
    """An empty `full_file_content` must not be silently replaced with the pre-edit fragment.

    Regression for loop1-8: the `or` short-circuit at the thin-wrapper call
    site treated `""` identically to `None`, so an Edit collapsing a file to
    empty was scanned against the pre-edit fragment instead of the empty
    post-edit content. Mirror the canonical idiom at line 3438.
    """
    pre_edit_fragment_with_imports_only = (
        "from real_module import do_thing\n__all__ = ['do_thing']\n"
    )
    issues = code_rules_enforcer.validate_content(
        pre_edit_fragment_with_imports_only,
        "/project/src/aliases.py",
        full_file_content="",
    )
    assert not any("thin wrapper" in each.lower() for each in issues), (
        f"empty post-edit file must not be flagged as a thin wrapper, got: {issues!r}"
    )


def test_isolation_check_does_not_flag_expanduser_without_tilde_argument() -> None:
    """expanduser of a tilde-free string does not probe HOME and must not fire."""
    source = (
        "import os\n"
        "def test_resolves_relative() -> None:\n"
        "    target = os.path.expanduser('relative/path')\n"
        "    assert target\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == [], f"tilde-free expanduser must not be flagged, got: {issues!r}"


def test_isolation_check_flags_expanduser_with_tilde_argument() -> None:
    """expanduser of a leading-tilde string resolves HOME and must fire."""
    source = (
        "import os\n"
        "def test_reads_home() -> None:\n"
        "    target = os.path.expanduser('~/.config/x')\n"
        "    assert target\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("expanduser" in each_issue for each_issue in issues)


def test_isolation_check_flags_path_constructor_expanduser_method() -> None:
    """`Path('~/x').expanduser()` expands the home directory through the bound
    Path object and must fire even though it bypasses the static probe chain."""
    source = (
        "from pathlib import Path\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = Path('~/x').expanduser()\n"
        "    target.read_text()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("expanduser" in each_issue for each_issue in issues)


def test_isolation_check_flags_aliased_path_constructor_expanduser_method() -> None:
    """`from pathlib import Path as P` then `P('~/x').expanduser()` resolves the
    constructor through alias canonicalization and must fire."""
    source = (
        "from pathlib import Path as P\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = P('~/x').expanduser()\n"
        "    target.read_text()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("expanduser" in each_issue for each_issue in issues)


def test_isolation_check_flags_tempfile_named_temporary_file() -> None:
    """`tempfile.NamedTemporaryFile()` allocates in the shared temp dir and must
    fire as a temp-isolation probe."""
    source = (
        "import tempfile\n"
        "def test_writes_named_temp() -> None:\n"
        "    handle = tempfile.NamedTemporaryFile()\n"
        "    handle.write(b'x')\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("NamedTemporaryFile" in each_issue for each_issue in issues)


def test_isolation_check_exempts_tempfile_factory_with_explicit_dir() -> None:
    """A tempfile factory given an explicit `dir=` argument allocates under the
    supplied sandbox, so it must not fire as a shared-temp isolation probe."""
    source = (
        "import tempfile\n"
        "def test_writes_named_temp(tmp_path) -> None:\n"
        "    handle = tempfile.NamedTemporaryFile(dir=tmp_path)\n"
        "    handle.write(b'x')\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == []


def test_isolation_check_flags_tempfile_factory_with_dir_constant_none() -> None:
    """`dir=None` selects the default shared temp directory, so the factory
    still allocates from shared temp and must fire."""
    source = (
        "import tempfile\n"
        "def test_writes_named_temp() -> None:\n"
        "    handle = tempfile.NamedTemporaryFile(dir=None)\n"
        "    handle.write(b'x')\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("NamedTemporaryFile" in each_issue for each_issue in issues)


def test_isolation_check_flags_tempfile_factory_with_dir_getenv_tmpdir() -> None:
    """`dir=os.getenv('TMPDIR')` resolves to a shared-temp env source, so the
    factory still allocates from shared temp and must fire."""
    source = (
        "import os\n"
        "import tempfile\n"
        "def test_makes_temp_dir() -> None:\n"
        "    holder = tempfile.mkdtemp(dir=os.getenv('TMPDIR'))\n"
        "    print(holder)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("mkdtemp" in each_issue for each_issue in issues)


def test_isolation_check_exempts_tempfile_factory_with_dir_tmp_path() -> None:
    """`dir=tmp_path` allocates under the pytest sandbox, so the factory is
    isolated and must not fire."""
    source = (
        "import tempfile\n"
        "def test_makes_temp_dir(tmp_path) -> None:\n"
        "    holder = tempfile.mkdtemp(dir=tmp_path)\n"
        "    print(holder)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == []


def test_isolation_check_flags_class_level_probe_in_nested_class_body() -> None:
    """A Path.home() initializer in a nested class body runs at class-creation
    time during the test, so it must fire."""
    source = (
        "from pathlib import Path\n"
        "def test_defines_inner_class() -> None:\n"
        "    class Inner:\n"
        "        root = Path.home()\n"
        "    assert Inner is not None\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("Path.home" in each_issue for each_issue in issues)


def test_isolation_check_flags_from_os_import_path_expanduser() -> None:
    """`from os import path` binds `path` to `os.path`, so `path.expanduser`
    must resolve to the canonical `os.path.expanduser` probe and fire."""
    source = (
        "from os import path\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = path.expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("expanduser" in each_issue for each_issue in issues)


def test_isolation_check_flags_expandvars_with_windows_percent_userprofile() -> None:
    """expandvars expands Windows `%USERPROFILE%` percent syntax, so a percent
    reference to a home env var must fire."""
    source = (
        "import os\n"
        "def test_expands_userprofile() -> None:\n"
        "    target = os.path.expandvars('%USERPROFILE%\\\\.cfg')\n"
        "    open(target).read()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("expandvars" in each_issue for each_issue in issues)


def test_isolation_check_ignores_expandvars_with_unrelated_windows_percent_var() -> None:
    """A percent reference to an unrelated env var does not probe HOME/TMP and
    must not fire."""
    source = (
        "import os\n"
        "def test_expands_unrelated() -> None:\n"
        "    token = os.path.expandvars('%MY_APP_TOKEN%')\n"
        "    print(token)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == []


def test_isolation_check_flags_environ_get_via_local_binding() -> None:
    """`e = os.environ` then `e.get('HOME')` reads HOME through a local alias
    and must fire just like the subscript `e['HOME']` form."""
    source = (
        "import os\n"
        "def test_resolves_home() -> None:\n"
        "    e = os.environ\n"
        "    home = e.get('HOME')\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("HOME" in each_issue for each_issue in issues)


def test_isolation_check_scopes_path_bindings_to_their_own_test() -> None:
    """A `p = Path('~/x')` binding in one test must not make an unrelated
    `p.expanduser()` in a sibling test a finding; bindings are per-test."""
    source = (
        "from pathlib import Path\n"
        "def test_a() -> None:\n"
        "    p = Path('~/x')\n"
        "    p.expanduser()\n"
        "def test_b(p) -> None:\n"
        "    p.expanduser()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("test_a" in each_issue for each_issue in issues)
    assert not any("test_b" in each_issue for each_issue in issues)


def test_isolation_check_scopes_environ_bindings_to_their_own_test() -> None:
    """An `e = os.environ` binding in one test must not make an unrelated
    `e['HOME']` in a sibling test a finding; bindings are per-test."""
    source = (
        "import os\n"
        "def test_a() -> None:\n"
        "    e = os.environ\n"
        "    home = e['HOME']\n"
        "    print(home)\n"
        "def test_b(e) -> None:\n"
        "    home = e['HOME']\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("test_a" in each_issue for each_issue in issues)
    assert not any("test_b" in each_issue for each_issue in issues)


def test_isolation_check_ignores_path_constructor_expanduser_with_tilde_free_argument() -> None:
    """`Path('/tmp/x').expanduser()` carries no leading tilde, so it expands no
    home directory and must stay symmetric with `os.path.expanduser` of a
    tilde-free literal — neither fires."""
    source = (
        "from pathlib import Path\n"
        "def test_resolves_absolute() -> None:\n"
        "    target = Path('/tmp/x').expanduser()\n"
        "    target.read_text()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == []


def test_isolation_check_ignores_static_pathlib_expanduser_with_dynamic_argument() -> None:
    """`pathlib.Path.expanduser(some_path)` with a non-constant argument cannot
    be inspected for a leading tilde, so it follows the conservative rule and
    does not fire — symmetric with `os.path.expanduser(some_path)`."""
    source = (
        "import pathlib\n"
        "def test_resolves_dynamic(some_path) -> None:\n"
        "    target = pathlib.Path.expanduser(some_path)\n"
        "    target.read_text()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == []


def test_isolation_check_flags_path_home_via_function_local_class_alias() -> None:
    """`path_class = Path` then `path_class.home()` reaches the real home
    directory through a per-test class alias and must fire just like the bare
    `Path.home()` form."""
    source = (
        "from pathlib import Path\n"
        "def test_reads_home() -> None:\n"
        "    path_class = Path\n"
        "    home_dir = path_class.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("home" in each_issue.lower() for each_issue in issues)


def test_isolation_check_flags_getenv_via_function_local_callable_alias() -> None:
    """`read_env = os.getenv` then `read_env('HOME')` reads HOME through a
    per-test callable alias and must fire just like the bare `os.getenv('HOME')`
    form."""
    source = (
        "import os\n"
        "def test_reads_home() -> None:\n"
        "    read_env = os.getenv\n"
        "    home = read_env('HOME')\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("HOME" in each_issue for each_issue in issues)


def test_isolation_check_flags_tempfile_spooled_temporary_file() -> None:
    """`tempfile.SpooledTemporaryFile()` allocates in the shared temp dir and
    must fire as a temp-isolation probe alongside the other tempfile factories."""
    source = (
        "import tempfile\n"
        "def test_writes_spooled_temp() -> None:\n"
        "    handle = tempfile.SpooledTemporaryFile()\n"
        "    handle.write(b'x')\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("SpooledTemporaryFile" in each_issue for each_issue in issues)


def test_isolation_check_flags_tempfile_gettempdirb() -> None:
    """`tempfile.gettempdirb()` returns the shared temp dir as bytes and must
    fire just like the string-returning `tempfile.gettempdir()`."""
    source = (
        "import tempfile\n"
        "def test_resolves_temp_bytes() -> None:\n"
        "    base = tempfile.gettempdirb()\n"
        "    print(base)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("gettempdirb" in each_issue for each_issue in issues)


def test_isolation_check_flags_module_level_from_os_import_environ_subscript() -> None:
    """A module-level `from os import environ` binds `environ` to `os.environ`,
    so `environ['HOME']` inside a test must fire even without a per-test
    local binding."""
    source = (
        "from os import environ\n"
        "def test_resolves_home() -> None:\n"
        "    home = environ['HOME']\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("HOME" in each_issue for each_issue in issues)


def test_isolation_check_reports_probes_in_source_order_on_new_file() -> None:
    """On a new file (``all_changed_lines is None``) every probe is in scope and
    reported in source order — none dropped by the cap, which now trims only
    out-of-scope advisory noise."""
    probe_count = 20
    repeated_probes = "\n".join(
        f"    p{each_index} = Path.home()" for each_index in range(probe_count)
    )
    source = (
        f"from pathlib import Path\ndef test_many_probes() -> None:\n{repeated_probes}\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    first_probe_line_number = 3
    reported_line_numbers = [
        int(each_issue.split(":", maxsplit=1)[0].removeprefix("Line ").strip())
        for each_issue in issues
    ]
    expected_line_numbers = [
        first_probe_line_number + each_offset for each_offset in range(probe_count)
    ]
    assert reported_line_numbers == expected_line_numbers


def test_exempt_comment_rejects_noqa_prefixed_prose_lacking_boundary() -> None:
    """A comment body that merely starts with `noqa` followed by non-boundary
    characters is not a real noqa directive and must stay subject to the
    no-new-comments rule."""
    source = "x = compute()  # noqa-but-not-really: explanation\n"
    issues = code_rules_enforcer.check_comments_python(source)
    assert issues


def test_exempt_comment_keeps_bare_and_coded_noqa_exempt() -> None:
    """A bare `# noqa` and a coded `# noqa: E501` remain exempt under the
    tightened boundary rule."""
    bare_source = "x = compute()  # noqa\n"
    coded_source = "x = compute()  # noqa: E501\n"
    assert code_rules_enforcer.check_comments_python(bare_source) == []
    assert code_rules_enforcer.check_comments_python(coded_source) == []


def test_exempt_comment_keeps_colon_terminated_markers_without_trailing_space() -> None:
    """A colon-terminated marker (`pylint:`, `type:`, `pragma:`) is self-bounded
    by its own colon, so the directive stays exempt even when the next character
    follows the colon immediately."""
    pylint_source = "import os  # pylint:disable=unused-import\n"
    type_ignore_source = "x = compute()  # type:ignore\n"
    pragma_source = "x = compute()  # pragma:no-cover\n"
    assert code_rules_enforcer.check_comments_python(pylint_source) == []
    assert code_rules_enforcer.check_comments_python(type_ignore_source) == []
    assert code_rules_enforcer.check_comments_python(pragma_source) == []


def test_exempt_comment_still_flags_noqa_glued_to_prose_without_boundary() -> None:
    """The colon-terminated allowance must not loosen the boundary rule for
    markers that do not end in a colon: `# noqaFOO` still lacks a real boundary
    after `noqa` and stays subject to the no-new-comments rule."""
    source = "x = compute()  # noqaFOO\n"
    assert code_rules_enforcer.check_comments_python(source)


def test_banned_noun_word_skips_non_aliased_upstream_import() -> None:
    """A non-aliased upstream import the author cannot rename
    (`from typing import ItemsView`) must not be flagged, while an
    author-coined alias still is."""
    production_path = "packages/myapp/services/customer_pipeline.py"
    upstream_issues = code_rules_enforcer.check_banned_noun_word_boundary(
        "from typing import ItemsView\n", production_path
    )
    aliased_issues = code_rules_enforcer.check_banned_noun_word_boundary(
        "import legacy_helper as cached_response\n", production_path
    )
    assert upstream_issues == []
    assert any("cached_response" in each_issue for each_issue in aliased_issues)


def test_function_length_message_does_not_cite_file_length_section() -> None:
    """The blocking message must cite a function-length basis, not the
    advisory file-length section (CODE_RULES §6.5)."""
    assert "6.5" not in code_rules_enforcer.FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX
    assert "Clean Code" in code_rules_enforcer.FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX


def _function_node_named(source: str, function_name: str) -> ast.FunctionDef:
    syntax_tree = ast.parse(source)
    for each_node in syntax_tree.body:
        if isinstance(each_node, ast.FunctionDef) and each_node.name == function_name:
            return each_node
    raise AssertionError(f"no function named {function_name!r} in source")


def test_collect_pathlib_path_bindings_only_sees_the_scope_node_function() -> None:
    """The Path-binding collector must scope its walk to the function node it
    is given. A `p = Path('~/x')` binding in test_a must not appear when the
    collector is handed test_b's node (test_b never binds `p` to a Path)."""
    source = (
        "from pathlib import Path\n"
        "def test_a() -> None:\n"
        "    p = Path('~/x')\n"
        "    p.expanduser()\n"
        "def test_b(p) -> None:\n"
        "    p.expanduser()\n"
    )
    syntax_tree = ast.parse(source)
    alias_map = code_rules_enforcer._build_alias_canonicalization_map(syntax_tree)
    test_a_node = _function_node_named(source, "test_a")
    test_b_node = _function_node_named(source, "test_b")

    test_a_bindings = code_rules_enforcer._collect_pathlib_path_local_binding_names(
        test_a_node, alias_map
    )
    test_b_bindings = code_rules_enforcer._collect_pathlib_path_local_binding_names(
        test_b_node, alias_map
    )

    assert "p" in test_a_bindings
    assert "p" not in test_b_bindings


def test_collect_os_environ_bindings_only_sees_the_scope_node_function() -> None:
    """The environ-binding collector must scope its walk to the function node
    it is given. An `e = os.environ` binding in test_a must not appear when the
    collector is handed test_b's node (test_b never binds `e`)."""
    source = (
        "import os\n"
        "def test_a() -> None:\n"
        "    e = os.environ\n"
        "    home = e['HOME']\n"
        "    print(home)\n"
        "def test_b(e) -> None:\n"
        "    home = e['HOME']\n"
        "    print(home)\n"
    )
    syntax_tree = ast.parse(source)
    alias_map = code_rules_enforcer._build_alias_canonicalization_map(syntax_tree)
    test_a_node = _function_node_named(source, "test_a")
    test_b_node = _function_node_named(source, "test_b")

    test_a_bindings = code_rules_enforcer._collect_os_environ_local_binding_names(
        test_a_node, alias_map
    )
    test_b_bindings = code_rules_enforcer._collect_os_environ_local_binding_names(
        test_b_node, alias_map
    )

    assert "e" in test_a_bindings
    assert "e" not in test_b_bindings


def test_function_local_from_os_import_environ_does_not_leak_into_sibling_test() -> None:
    """bugbot-1: a function-local `from os import environ` in test_a binds
    `environ` only for test_a's runtime. A sibling test_b that references the
    bare name `environ` without importing it must not be flagged, while the
    test that actually imports and probes HOME (test_a) must be flagged."""
    source = (
        "def test_a() -> None:\n"
        "    from os import environ\n"
        "    home = environ['HOME']\n"
        "    print(home)\n"
        "def test_b() -> None:\n"
        "    home = environ['HOME']\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("test_a" in each_issue for each_issue in issues), (
        f"test_a's own function-local environ import must be flagged, got: {issues!r}"
    )
    assert not any("test_b" in each_issue for each_issue in issues), (
        "test_b references bare `environ` it never imports, so the function-local "
        f"import in test_a must not leak into it, got: {issues!r}"
    )


def test_function_local_aliased_module_import_does_not_leak_into_sibling_test() -> None:
    """bugbot-1 sibling: a function-local `import os as o` in test_a aliases
    `o` only for test_a. test_b referencing `o.getenv('HOME')` without its own
    import must not be flagged; test_a's own probe must be flagged."""
    source = (
        "def test_a() -> None:\n"
        "    import os as o\n"
        "    home = o.getenv('HOME')\n"
        "    print(home)\n"
        "def test_b() -> None:\n"
        "    home = o.getenv('HOME')\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("test_a" in each_issue for each_issue in issues), (
        f"test_a's own function-local aliased import must be flagged, got: {issues!r}"
    )
    assert not any("test_b" in each_issue for each_issue in issues), (
        "test_b references alias `o` it never bound, so the function-local "
        f"import in test_a must not leak into it, got: {issues!r}"
    )


def test_build_alias_map_excludes_function_local_imports() -> None:
    """bugbot-1: the module-wide alias canonicalization map must be built only
    from top-level imports. A function-local `import os as o` and a
    function-local `from os import environ` must not appear in the shared map."""
    source = (
        "import tempfile as module_temp\n"
        "def test_a() -> None:\n"
        "    import os as o\n"
        "    from os import environ\n"
        "    print(o, environ)\n"
    )
    syntax_tree = ast.parse(source)
    alias_map = code_rules_enforcer._build_alias_canonicalization_map(syntax_tree)
    assert alias_map.get("module_temp") == "tempfile", (
        f"top-level alias must be recorded, got: {alias_map!r}"
    )
    assert "o" not in alias_map, (
        f"function-local `import os as o` must not leak into the module map, got: {alias_map!r}"
    )
    assert "environ" not in alias_map, (
        f"function-local `from os import environ` must not leak into the module map, got: {alias_map!r}"
    )


def test_module_level_from_os_import_environ_still_flags_every_referencing_test() -> None:
    """bugbot-1 guard: a genuine module-level `from os import environ` binds the
    name for the whole module, so every test that probes HOME through it must
    still be flagged. The per-function scoping must not suppress this case."""
    source = (
        "from os import environ\n"
        "def test_a() -> None:\n"
        "    print(environ['HOME'])\n"
        "def test_b() -> None:\n"
        "    print(environ['HOME'])\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("test_a" in each_issue for each_issue in issues)
    assert any("test_b" in each_issue for each_issue in issues), (
        f"module-level import must flag every probing test, got: {issues!r}"
    )


def test_build_alias_map_excludes_class_body_imports() -> None:
    """A probe alias imported inside a class body binds only inside that class
    scope, so it must not enter the module-wide alias canonicalization map. A
    genuine module-level alias in the same source must still be recorded."""
    source = (
        "import tempfile as module_temp\n"
        "class TestAlpha:\n"
        "    import tempfile as t\n"
        "    def test_alpha_probe(self) -> None:\n"
        "        assert self.t is not None\n"
    )
    syntax_tree = ast.parse(source)
    alias_map = code_rules_enforcer._build_alias_canonicalization_map(syntax_tree)
    assert alias_map.get("module_temp") == "tempfile", (
        f"top-level alias must be recorded, got: {alias_map!r}"
    )
    assert "t" not in alias_map, (
        f"class-body `import tempfile as t` must not leak into the module map, got: {alias_map!r}"
    )


def test_class_body_aliased_import_does_not_leak_into_sibling_test() -> None:
    """A class-body `import tempfile as t` aliases `t` only inside that class.
    A sibling top-level test taking `t` as a parameter and calling `t.mkdtemp()`
    must not be flagged, since the class-scoped alias never enters the
    module-wide map."""
    source = (
        "class TestAlpha:\n"
        "    import tempfile as t\n"
        "    def test_alpha_probe(self) -> None:\n"
        "        assert self.t is not None\n"
        "def test_sibling(t) -> None:\n"
        "    t.mkdtemp()\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert not any("test_sibling" in each_issue for each_issue in issues), (
        "class-body alias must not leak into a sibling test through the "
        f"module-wide map, got: {issues!r}"
    )


def test_build_alias_map_records_module_top_level_but_excludes_function_and_class_imports() -> None:
    """Only true module-top-level imports enter the alias map. Imports lexically
    inside a function body or a class body are excluded, while a module-level
    try-guarded optional import is still recorded module-wide."""
    source = (
        "try:\n"
        "    import tempfile as guarded_temp\n"
        "except ImportError:\n"
        "    guarded_temp = None\n"
        "def test_function_local() -> None:\n"
        "    import tempfile as function_temp\n"
        "    assert function_temp is not None\n"
        "class TestBeta:\n"
        "    import tempfile as class_temp\n"
        "    def test_beta_probe(self) -> None:\n"
        "        assert self.class_temp is not None\n"
    )
    syntax_tree = ast.parse(source)
    alias_map = code_rules_enforcer._build_alias_canonicalization_map(syntax_tree)
    assert alias_map.get("guarded_temp") == "tempfile", (
        f"module-level try-guarded alias must be recorded, got: {alias_map!r}"
    )
    assert "function_temp" not in alias_map, (
        f"function-local alias must not enter the module map, got: {alias_map!r}"
    )
    assert "class_temp" not in alias_map, (
        f"class-body alias must not enter the module map, got: {alias_map!r}"
    )


def _oversized_function_source(name: str) -> str:
    body_line_count = code_rules_enforcer.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    body_lines = [
        f"    bound_{each_index} = {each_index}" for each_index in range(body_line_count)
    ]
    return f"def {name}() -> None:\n" + "\n".join(body_lines) + "\n"


def test_function_length_edit_does_not_block_untouched_long_function() -> None:
    """loop5-1: editing a short region of a file that already contains an
    untouched oversized function must not produce a blocking function-length
    violation at the PreToolUse layer."""
    untouched_long_function = _oversized_function_source("untouched_long")
    short_helper_before = "def short_helper() -> int:\n    return 1\n"
    short_helper_after = "def short_helper() -> int:\n    return 2\n"
    prior_full_file = untouched_long_function + "\n" + short_helper_before
    post_edit_full_file = untouched_long_function + "\n" + short_helper_after
    issues = code_rules_enforcer.validate_content(
        short_helper_after,
        "/project/src/edited_module.py",
        old_content=short_helper_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert not any(
        "untouched_long" in each_issue for each_issue in issues
    ), f"untouched long function must not block on an unrelated edit, got: {issues!r}"


def test_function_length_edit_blocks_function_grown_on_changed_lines() -> None:
    """loop5-1: when the edit itself grows a function past the threshold, the
    function-length violation must still block at the PreToolUse layer."""
    short_function_before = "def grows_now() -> int:\n    return 1\n"
    grown_function_after = _oversized_function_source("grows_now")
    prior_full_file = short_function_before
    post_edit_full_file = grown_function_after
    issues = code_rules_enforcer.validate_content(
        grown_function_after,
        "/project/src/edited_module.py",
        old_content=short_function_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert any(
        "grows_now" in each_issue for each_issue in issues
    ), f"function grown past threshold on changed lines must block, got: {issues!r}"


def test_isolation_edit_does_not_block_untouched_probe() -> None:
    """loop5-3: editing a short region of a test file that already contains an
    untouched HOME probe must not block at the PreToolUse layer."""
    untouched_probe_function = (
        "def test_reads_home() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    short_test_before = "def test_addition() -> None:\n    assert 1 + 1 == 2\n"
    short_test_after = "def test_addition() -> None:\n    assert 2 + 2 == 4\n"
    header = "from pathlib import Path\n"
    prior_full_file = header + untouched_probe_function + "\n" + short_test_before
    post_edit_full_file = header + untouched_probe_function + "\n" + short_test_after
    issues = code_rules_enforcer.validate_content(
        short_test_after,
        "/project/src/test_edited_module.py",
        old_content=short_test_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert not any(
        "test_reads_home" in each_issue for each_issue in issues
    ), f"untouched isolation probe must not block on an unrelated edit, got: {issues!r}"


def test_isolation_edit_blocks_probe_added_on_changed_lines() -> None:
    """loop5-3: when the edit introduces a HOME probe, the isolation violation
    must still block at the PreToolUse layer."""
    test_before = "def test_writes() -> None:\n    assert True\n"
    test_after = (
        "def test_writes() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    header = "from pathlib import Path\n"
    prior_full_file = header + test_before
    post_edit_full_file = header + test_after
    issues = code_rules_enforcer.validate_content(
        test_after,
        "/project/src/test_edited_module.py",
        old_content=test_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert any(
        "test_writes" in each_issue and "Path.home" in each_issue
        for each_issue in issues
    ), f"isolation probe added on changed lines must block, got: {issues!r}"


def test_isolation_edit_blocks_probe_unisolated_by_signature_line_change() -> None:
    """Removing the ``monkeypatch`` fixture from a test's signature line
    un-isolates a HOME probe in its unchanged body; the violation must block
    because the enclosing function's span covers the changed signature line."""
    test_before = (
        "def test_reads_home(monkeypatch) -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    test_after = (
        "def test_reads_home() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    header = "from pathlib import Path\n"
    prior_full_file = header + test_before
    post_edit_full_file = header + test_after
    issues = code_rules_enforcer.validate_content(
        test_after,
        "/project/src/test_edited_module.py",
        old_content=test_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert any(
        "test_reads_home" in each_issue and "Path.home" in each_issue
        for each_issue in issues
    ), f"signature-line change that un-isolates a probe must block, got: {issues!r}"


def test_isolation_message_carries_enclosing_function_definition_span() -> None:
    """The isolation message must carry the enclosing test's definition line
    and line span so the commit gate can scope by the same function span the
    enforcer uses, while keeping the ``Line N:`` probe-line prefix intact."""
    header = "from pathlib import Path\n"
    test_body = (
        "def test_reads_home() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    source = header + test_body
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    definition_line = 2
    function_span = 3
    expected_span_fragment = (
        f"(defined at line {definition_line}, spanning {function_span} lines)"
    )
    assert any(
        each_issue.startswith("Line ") and expected_span_fragment in each_issue
        for each_issue in issues
    ), f"isolation message must carry the def-line + span fragment, got: {issues!r}"


def test_function_length_reports_only_in_scope_violation_on_terminal_edit() -> None:
    """A terminal diff-scoped Edit reports only the function whose changed-line
    span grew past the threshold; untouched oversized functions earlier in the
    file are out of scope and dropped, regardless of how many precede it."""
    leading_function_count = 6
    leading_functions = "\n".join(
        _oversized_function_source(f"leading_long_{each_index}")
        for each_index in range(leading_function_count)
    )
    short_target_before = "def target_function() -> int:\n    return 1\n"
    grown_target_after = _oversized_function_source("target_function")
    prior_full_file = leading_functions + "\n" + short_target_before
    post_edit_full_file = leading_functions + "\n" + grown_target_after
    issues = code_rules_enforcer.validate_content(
        grown_target_after,
        "/project/src/many_functions.py",
        old_content=short_target_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    function_length_issues = [
        each_issue for each_issue in issues if "defined at line" in each_issue
    ]
    assert any(
        "target_function" in each_issue for each_issue in function_length_issues
    ), f"in-scope grown function must still block, got: {issues!r}"
    assert not any(
        "leading_long_" in each_issue for each_issue in function_length_issues
    ), f"untouched functions must stay out of scope, got: {function_length_issues!r}"


def test_new_file_write_reports_every_in_scope_long_function_uncapped() -> None:
    """loop7-bugbot: a new-file Write passes ``all_changed_lines is None``; every
    line was just authored and is in scope, so every long function is reported
    with no ceiling on the count."""
    function_count = 6
    all_functions = "\n".join(
        _oversized_function_source(f"new_long_{each_index}")
        for each_index in range(function_count)
    )
    issues = code_rules_enforcer.validate_content(
        all_functions,
        "/project/src/freshly_written_module.py",
        old_content="",
    )
    function_length_issues = [
        each_issue for each_issue in issues if "defined at line" in each_issue
    ]
    assert len(function_length_issues) == function_count, (
        "every long function in a new file is in scope and must be reported, "
        f"got: {function_length_issues!r}"
    )


def test_new_file_write_reports_every_in_scope_isolation_probe_uncapped() -> None:
    """loop7-bugbot: a new test file Write passes ``all_changed_lines is None``;
    every HOME probe is in scope, so each one is reported with no count ceiling."""
    probe_count = 6
    probing_tests = "".join(
        f"def test_probe_{each_index}() -> None:\n"
        f"    home_dir_{each_index} = Path.home()\n"
        f"    assert home_dir_{each_index}\n"
        for each_index in range(probe_count)
    )
    source = "from pathlib import Path\n" + probing_tests
    issues = code_rules_enforcer.validate_content(
        source,
        "/project/src/test_freshly_written_module.py",
        old_content="",
    )
    home_probe_issues = [
        each_issue for each_issue in issues if "Path.home" in each_issue
    ]
    assert len(home_probe_issues) == probe_count, (
        "every HOME probe in a new test file is in scope and must be reported, "
        f"got: {home_probe_issues!r}"
    )


def test_banned_noun_word_defers_scope_to_caller_when_requested() -> None:
    """loop7-P1: when the gate sets the deferral flag, the banned-noun check must
    return every violation so ``split_violations_by_scope`` can scope by added
    line before reporting the in-scope set."""
    binding_count = 5
    source = "".join(
        f"BINDING_{each_index}_RESULT_PATH = {each_index}\n"
        for each_index in range(binding_count)
    )
    issues = code_rules_enforcer.check_banned_noun_word_boundary(
        source,
        "/project/src/many_nouns.py",
        defer_scope_to_caller=True,
    )
    assert len(issues) == binding_count, (
        "deferral must return every banned-noun violation, "
        f"got: {issues!r}"
    )


def test_banned_noun_word_keeps_in_scope_binding_among_untouched_ones() -> None:
    """loop7-P1: an Edit whose changed line introduces a banned-noun identifier
    among several pre-existing untouched ones must still report the new in-scope
    binding while leaving the untouched bindings out of scope."""
    leading_count = 5
    leading_bindings = "".join(
        f"LEADING_{each_index}_RESULT_PATH = {each_index}\n"
        for each_index in range(leading_count)
    )
    target_before = "PLACEHOLDER_NAME = 0\n"
    target_after = "INTRODUCED_RESULT_PATH = 0\n"
    prior_full_file = leading_bindings + target_before
    post_edit_full_file = leading_bindings + target_after
    issues = code_rules_enforcer.validate_content(
        target_after,
        "/project/src/many_nouns.py",
        old_content=target_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert any(
        "INTRODUCED_RESULT_PATH" in each_issue for each_issue in issues
    ), f"in-scope banned-noun past the cap window must still block, got: {issues!r}"


def test_module_import_inside_top_level_try_is_retained_in_alias_map() -> None:
    """loop7-P2 (2566): a module-level ``try: import os as o`` is genuinely
    module-scoped; its alias must enter the shared canonicalization map so a
    later ``o.path.expanduser('~')`` inside a test is flagged."""
    source = (
        "try:\n"
        "    import os as o\n"
        "except ImportError:\n"
        "    o = None\n"
        "def test_reads_home() -> None:\n"
        "    discovered = o.path.expanduser('~')\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_optional_import.py"
    )
    assert any(
        "test_reads_home" in each_issue for each_issue in issues
    ), f"module import nested in top-level try must be retained, got: {issues!r}"


def test_direct_module_aliased_import_is_retained_in_alias_map() -> None:
    """loop7-P2 (2566): a plain top-level ``import os as o`` must still resolve so
    ``o.path.expanduser('~')`` inside a test is flagged."""
    source = (
        "import os as o\n"
        "def test_reads_home() -> None:\n"
        "    discovered = o.path.expanduser('~')\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_direct_import.py"
    )
    assert any(
        "test_reads_home" in each_issue for each_issue in issues
    ), f"direct module aliased import must resolve, got: {issues!r}"


def test_function_local_import_does_not_enter_shared_alias_map() -> None:
    """loop7-P2 (2566): an import inside one test must not canonicalize a
    same-named reference in a sibling test that never imported it."""
    source = (
        "def test_imports_locally() -> None:\n"
        "    import os as o\n"
        "    assert o\n"
        "def test_sibling_uses_o() -> None:\n"
        "    o = make_unrelated_object()\n"
        "    discovered = o.path.expanduser('~')\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_local_import_scope.py"
    )
    assert not any(
        "test_sibling_uses_o" in each_issue for each_issue in issues
    ), f"function-local import must not leak to a sibling test, got: {issues!r}"


def test_import_inside_nested_helper_does_not_leak_to_outer_test_overlay() -> None:
    """loop7-P2 (2690): an import inside a standalone nested helper runs in its own
    callable scope; its alias must not enter the outer test's overlay and flag a
    sibling reference in the outer body."""
    source = (
        "def test_outer() -> None:\n"
        "    def nested_helper() -> None:\n"
        "        import os as o\n"
        "        assert o\n"
        "    o = make_unrelated_object()\n"
        "    discovered = o.path.expanduser('~')\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_nested_helper_scope.py"
    )
    assert not any(
        "test_outer" in each_issue for each_issue in issues
    ), f"nested-helper import must not leak to the outer test, got: {issues!r}"


def test_environ_binding_inside_nested_helper_does_not_leak_to_outer_test() -> None:
    """loop7-P2 (2690 sibling): an ``os.environ`` binding inside a standalone
    nested helper runs in its own scope; a same-named outer reference must not be
    attributed to that binding."""
    source = (
        "import os\n"
        "def test_outer() -> None:\n"
        "    def nested_helper() -> None:\n"
        "        captured = os.environ\n"
        "        assert captured\n"
        "    captured = make_unrelated_mapping()\n"
        "    discovered = captured['HOME']\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_environ_nested_scope.py"
    )
    assert not any(
        "test_outer" in each_issue for each_issue in issues
    ), f"nested-helper environ binding must not leak to the outer test, got: {issues!r}"


def test_pathlib_binding_inside_nested_helper_does_not_leak_to_outer_test() -> None:
    """loop7-P2 (2690 sibling): a home-tilde ``Path('~')`` binding inside a
    standalone nested helper runs in its own scope; a same-named outer
    ``.expanduser()`` call must not be attributed to that binding."""
    source = (
        "from pathlib import Path\n"
        "def test_outer() -> None:\n"
        "    def nested_helper() -> None:\n"
        "        candidate = Path('~/config')\n"
        "        assert candidate\n"
        "    candidate = make_unrelated_path()\n"
        "    discovered = candidate.expanduser()\n"
        "    assert discovered\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_pathlib_nested_scope.py"
    )
    assert not any(
        "test_outer" in each_issue for each_issue in issues
    ), f"nested-helper pathlib binding must not leak to the outer test, got: {issues!r}"


def test_banned_noun_edit_drops_untouched_out_of_scope_binding() -> None:
    """An Edit that touches none of the banned-noun bindings reports nothing —
    the check now routes through the reconstructed effective content and the
    edit's changed lines, exactly like check_function_length, so an untouched
    binding outside the edit hunk must not block."""
    leading = "".join(
        f"LEADING_{each_index}_RESULT_PATH = {each_index}\n" for each_index in range(5)
    )
    edited_tail = "def compute_total() -> int:\n    running_sum = 0\n    return running_sum\n"
    prior_full_file = leading + "def compute_total() -> int:\n    running_sum = 0\n    return 0\n"
    post_edit_full_file = leading + edited_tail
    issues = code_rules_enforcer.validate_content(
        edited_tail,
        "/project/src/many_nouns.py",
        old_content="def compute_total() -> int:\n    running_sum = 0\n    return 0\n",
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert not any(
        "RESULT_PATH" in each_issue for each_issue in issues
    ), f"untouched banned-noun bindings must stay out of scope, got: {issues!r}"


def test_banned_noun_edit_keeps_touched_binding_in_scope() -> None:
    """An Edit whose changed line introduces a banned-noun binding reports it,
    using the reconstructed effective content and the edit's changed lines."""
    leading = "".join(
        f"LEADING_{each_index}_VALUE_PATH = {each_index}\n" for each_index in range(5)
    )
    prior_tail = "PLACEHOLDER_NAME = 0\n"
    edited_tail = "INTRODUCED_RESULT_PATH = 0\n"
    prior_full_file = leading + prior_tail
    post_edit_full_file = leading + edited_tail
    issues = code_rules_enforcer.validate_content(
        edited_tail,
        "/project/src/introduces_noun.py",
        old_content=prior_tail,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert any(
        "INTRODUCED_RESULT_PATH" in each_issue for each_issue in issues
    ), f"introduced banned-noun binding must block, got: {issues!r}"


def test_banned_noun_message_carries_binding_line_span() -> None:
    """A banned-noun binding carries its own binding line as a one-line span so
    the commit gate reconstructs it through the same shared span mechanism the
    other diff-scoped checks use, while keeping the Line N: prefix intact. The
    binding-line granularity matches the companion exact-match
    check_banned_identifiers and avoids re-flagging a pre-existing binding when
    an unrelated line of its enclosing function is edited."""
    source = (
        "def aggregate() -> list[int]:\n"
        "    canned_results = [1, 2, 3]\n"
        "    return canned_results\n"
    )
    issues = code_rules_enforcer.check_banned_noun_word_boundary(
        source, "/project/src/has_noun.py"
    )
    binding_line = 2
    expected_fragment = f"(binding span at line {binding_line}, spanning 1 lines)"
    assert any(
        each_issue.startswith(f"Line {binding_line}:") and expected_fragment in each_issue
        for each_issue in issues
    ), f"banned-noun message must carry the binding-line span fragment, got: {issues!r}"


def test_banned_noun_message_module_level_binding_spans_one_line() -> None:
    """A module-level banned-noun binding spans its own binding line alone
    (span 1)."""
    source = "SAFE_OUTPUT_PATH = '/var/run/x'\n"
    issues = code_rules_enforcer.check_banned_noun_word_boundary(
        source, "/project/src/module_noun.py"
    )
    expected_fragment = "(binding span at line 1, spanning 1 lines)"
    assert any(expected_fragment in each_issue for each_issue in issues), (
        f"module-level banned-noun span must be one line, got: {issues!r}"
    )


def test_banned_noun_edit_does_not_reflag_param_when_unrelated_body_line_changes() -> None:
    """Editing a body line of a function that already has a banned-noun
    parameter must not re-flag that pre-existing parameter: the binding-line
    span keeps the parameter out of scope unless its own declaration line is in
    the changed set."""
    prior_full_file = (
        "def transform(canned_results: int) -> int:\n"
        "    midpoint = canned_results\n"
        "    return midpoint\n"
    )
    post_edit_full_file = (
        "def transform(canned_results: int) -> int:\n"
        "    midpoint = canned_results + 1\n"
        "    return midpoint\n"
    )
    issues = code_rules_enforcer.validate_content(
        "    midpoint = canned_results + 1\n",
        "/project/src/has_param.py",
        old_content="    midpoint = canned_results\n",
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert not any(
        "canned_results" in each_issue for each_issue in issues
    ), f"pre-existing param must not re-flag on unrelated body edit, got: {issues!r}"


def test_unreadable_prior_yields_no_prior_and_no_reconstruction() -> None:
    """When the on-disk prior cannot be read for an Edit, the prior/post helper
    returns (None, None): a missing prior must not be fabricated as an empty
    string that would diff every line as changed and defeat edit scoping."""
    missing_path = "/project/src/does_not_exist_anywhere.py"
    prior_content, post_edit_content = code_rules_enforcer.prior_and_post_edit_content(
        missing_path,
        old_string="placeholder = 0\n",
        new_string="placeholder = 1\n",
    )
    assert prior_content is None
    assert post_edit_content is None


def test_readable_prior_yields_consistent_prior_and_reconstruction(tmp_path) -> None:
    """When the prior reads cleanly, the helper returns the same prior content it
    reconstructed the post-edit view from, so the two never diverge across two
    independent reads."""
    source_file = tmp_path / "module.py"
    original = "alpha = 1\nbeta = 2\n"
    source_file.write_text(original, encoding="utf-8")
    prior_content, post_edit_content = code_rules_enforcer.prior_and_post_edit_content(
        str(source_file),
        old_string="beta = 2\n",
        new_string="beta = 3\n",
    )
    assert prior_content == original
    assert post_edit_content == "alpha = 1\nbeta = 3\n"
    changed = code_rules_enforcer.changed_line_numbers(prior_content, post_edit_content)
    assert changed == {2}


def _run_main_with_edit_payload(
    file_path: str,
    old_string: str,
    new_string: str,
    monkeypatch: object,
    capsys: object,
) -> str:
    """Drive ``main()`` through its stdin entry point for an Edit and return stdout.

    Args:
        file_path: The on-disk path the Edit targets.
        old_string: The Edit's ``old_string`` fragment.
        new_string: The Edit's ``new_string`` fragment.
        monkeypatch: The pytest fixture used to redirect ``sys.stdin``.
        capsys: The pytest fixture used to capture the deny payload on stdout.

    Returns:
        The captured stdout, which holds the deny payload when violations fire.
    """
    edit_payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": file_path,
                "old_string": old_string,
                "new_string": new_string,
            },
        }
    )
    getattr(monkeypatch, "setattr")(code_rules_enforcer.sys, "stdin", io.StringIO(edit_payload))
    try:
        code_rules_enforcer.main()
    except SystemExit:
        pass
    captured = getattr(capsys, "readouterr")()
    return captured.out


def test_edit_with_missing_old_string_runs_whole_file_against_on_disk_content(
    tmp_path_factory: object, monkeypatch: object, capsys: object,
) -> None:
    """When an Edit's old_string is absent from the file, ``prior_and_post_edit_content``
    yields ``(None, None)``; ``main()`` must analyze the real on-disk file whole-file
    rather than the new_string fragment, so an oversized function elsewhere in the
    file is still reported with its true line numbers."""
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    untouched_long_function = _oversized_function_source("untouched_long")
    short_helper = "def short_helper() -> int:\n    return 1\n"
    on_disk_content = untouched_long_function + "\n" + short_helper
    source_file = production_directory / "edited_module.py"
    source_file.write_text(on_disk_content, encoding="utf-8")
    absent_fragment_old = "def absent_function() -> int:\n    return 0\n"
    short_fragment_new = "def absent_function() -> int:\n    return 2\n"
    stdout = _run_main_with_edit_payload(
        str(source_file), absent_fragment_old, short_fragment_new, monkeypatch, capsys,
    )
    assert "untouched_long" in stdout, (
        "an unreconstructable Edit must fall back to whole-file on-disk analysis, "
        f"so the oversized function is still reported; got stdout: {stdout!r}"
    )


def test_edit_with_unreadable_file_does_not_analyze_fragment_as_whole_file(
    tmp_path_factory: object, monkeypatch: object, capsys: object,
) -> None:
    """When the on-disk file cannot be read, no well-defined post-edit content
    exists; ``main()`` must exit cleanly rather than analyze the new_string
    fragment as if it were the whole file, so the fragment's own function-length
    violation does not surface as a deny payload."""
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    missing_path = str(production_directory / "never_created.py")
    oversized_fragment_old = "def grows() -> int:\n    return 0\n"
    oversized_fragment_new = _oversized_function_source("grows")
    stdout = _run_main_with_edit_payload(
        missing_path,
        oversized_fragment_old,
        oversized_fragment_new,
        monkeypatch,
        capsys,
    )
    assert stdout == "", (
        "an unreadable Edit target has no well-defined whole-file content, so the "
        f"fragment must not be analyzed as the whole file; got stdout: {stdout!r}"
    )


def test_isolation_check_exempts_usefixtures_monkeypatch_decorator() -> None:
    """A test isolated via ``@pytest.mark.usefixtures("monkeypatch")`` injects the
    monkeypatch fixture without a signature parameter and must be exempt from the
    HOME/TMP probe, mirroring the signature-parameter suppression."""
    source = (
        "import os\n"
        "import pytest\n"
        "@pytest.mark.usefixtures('monkeypatch')\n"
        "def test_reads_home() -> None:\n"
        "    home = os.environ['HOME']\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert issues == [], (
        "a test decorated with usefixtures('monkeypatch') is isolated and must "
        f"not be flagged; got: {issues!r}"
    )


def test_isolation_check_still_flags_usefixtures_without_monkeypatch() -> None:
    """``@pytest.mark.usefixtures("tmp_path")`` does not inject monkeypatch, so a
    HOME probe in its body must still be flagged."""
    source = (
        "import os\n"
        "import pytest\n"
        "@pytest.mark.usefixtures('tmp_path')\n"
        "def test_reads_home() -> None:\n"
        "    home = os.environ['HOME']\n"
        "    print(home)\n"
    )
    issues = code_rules_enforcer.check_tests_use_isolated_filesystem_paths(
        source, "/project/src/test_module.py"
    )
    assert any("HOME" in each_issue for each_issue in issues), (
        "usefixtures('tmp_path') does not intercept env reads, so the HOME probe "
        f"must still be flagged; got: {issues!r}"
    )


def test_banned_noun_word_boundary_flags_plural_results_identifier() -> None:
    """A plural banned noun ('results') embedded in an identifier must flag.

    ``ALL_BANNED_NOUN_WORDS`` contains plural forms (results, outputs,
    responses, values, items) in addition to the singular nouns, so an
    identifier such as ``canned_results`` is flagged even though no singular
    exact-match identifier appears.
    """
    source = "canned_results = []\n"
    issues = code_rules_enforcer.check_banned_noun_word_boundary(
        source, "/project/src/pipeline.py"
    )
    assert any("canned_results" in each_issue for each_issue in issues), (
        "a plural banned-noun identifier must be flagged by the word-boundary "
        f"check; got: {issues!r}"
    )
