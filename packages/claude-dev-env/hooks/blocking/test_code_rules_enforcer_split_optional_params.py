"""Behavior tests for the code_rules_optional_params code-rules check module."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_optional_params import (  # noqa: E402
    _build_fstring_skeleton,
    check_duplicated_format_patterns,
    check_unused_optional_parameters,
)

code_rules_enforcer = SimpleNamespace(
    _build_fstring_skeleton=_build_fstring_skeleton,
    check_duplicated_format_patterns=check_duplicated_format_patterns,
    check_unused_optional_parameters=check_unused_optional_parameters,
)


DUPLICATED_FORMAT_PRODUCTION_FILE_PATH = "packages/app/services/api_client.py"

DUPLICATED_FORMAT_TEST_FILE_PATH = "packages/app/tests/test_api_client.py"

KWARGS_EXPANSION_PRODUCTION_FILE_PATH = "packages/app/services/fetcher.py"

NESTED_FUNCTION_PRODUCTION_FILE_PATH = "packages/app/services/nested.py"

UNUSED_OPTIONAL_CONFIG_FILE_PATH = "packages/app/config/constants.py"

UNUSED_OPTIONAL_PRODUCTION_FILE_PATH = "packages/app/services/feature.py"

UNUSED_OPTIONAL_TEST_FILE_PATH = "packages/app/tests/test_feature.py"


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
