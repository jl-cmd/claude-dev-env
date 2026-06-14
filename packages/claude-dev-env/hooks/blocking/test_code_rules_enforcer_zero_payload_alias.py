"""Tests for check_zero_payload_function_alias — flag pass-through function aliases.

CODE_RULES §9.5 discourages indirection without payload. A function whose entire
body (after an optional docstring) is a single `return other_function(...)` that
forwards its own parameters unchanged to another function defined in the same
module is a second name for one behavior. Callers should invoke the real function
directly. This check operates at function granularity, complementing the
module-level thin-wrapper check.

Hook infrastructure is NOT exempt: pass-through aliases inside hook modules are
the original motivating case. Test files and config files remain exempt because
re-binding aliases are legitimate scaffolding there.
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


def check_zero_payload_function_alias(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_zero_payload_function_alias(content, file_path)


PRODUCTION_FILE_PATH = "/project/src/detection.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/detection.py"
TEST_FILE_PATH = "/project/src/test_detection.py"
CONFIG_FILE_PATH = "/project/config/detection.py"


def test_should_flag_pass_through_alias_forwarding_same_parameters() -> None:
    source = (
        "def find_bare_path_segments(content: str) -> set[str]:\n"
        "    return {part for part in content.split() if part}\n"
        "\n"
        "def find_bare_index_segments(content: str) -> set[str]:\n"
        "    return find_bare_path_segments(content)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert any("find_bare_index_segments" in each for each in issues), (
        f"Expected pass-through alias flag, got: {issues!r}"
    )


def test_should_flag_alias_inside_hook_infrastructure() -> None:
    source = (
        "def find_bare_path_segments(content: str) -> set[str]:\n"
        "    return {part for part in content.split() if part}\n"
        "\n"
        "def find_bare_index_segments(content: str) -> set[str]:\n"
        "    return find_bare_path_segments(content)\n"
    )
    issues = check_zero_payload_function_alias(source, HOOK_INFRASTRUCTURE_PATH)
    assert any("find_bare_index_segments" in each for each in issues), (
        f"Hook infrastructure is the motivating case and must be flagged, got: {issues!r}"
    )


def test_should_flag_alias_with_docstring_before_return() -> None:
    source = (
        "def compute_total(amount: int) -> int:\n"
        "    return amount * 2\n"
        "\n"
        "def calculate_total(amount: int) -> int:\n"
        '    """Forward to compute_total."""\n'
        "    return compute_total(amount)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert any("calculate_total" in each for each in issues), (
        f"A docstring before the single return must not hide the alias, got: {issues!r}"
    )


def test_should_not_flag_function_that_transforms_arguments() -> None:
    source = (
        "def find_bare_path_segments(content: str) -> set[str]:\n"
        "    return {part for part in content.split() if part}\n"
        "\n"
        "def find_stripped_segments(content: str) -> set[str]:\n"
        "    return find_bare_path_segments(content.strip())\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Transformed argument adds payload and must not be flagged, got: {issues!r}"
    )


def test_should_not_flag_function_that_reorders_arguments() -> None:
    source = (
        "def divide(numerator: int, denominator: int) -> float:\n"
        "    return numerator / denominator\n"
        "\n"
        "def inverse_divide(denominator: int, numerator: int) -> float:\n"
        "    return divide(numerator, denominator)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Reordered arguments change behavior and must not be flagged, got: {issues!r}"
    )


def test_should_not_flag_call_to_external_function() -> None:
    source = (
        "from other_module import real_helper\n"
        "\n"
        "def public_helper(value: int) -> int:\n"
        "    return real_helper(value)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A boundary wrapper around an imported function is not a same-module alias, "
        f"got: {issues!r}"
    )


def test_should_not_flag_method_call() -> None:
    source = (
        "def normalize(text: str) -> str:\n"
        "    return text.strip()\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A call to a method on a parameter is real work, got: {issues!r}"
    )


def test_should_not_flag_function_with_multiple_statements() -> None:
    source = (
        "def find_bare_path_segments(content: str) -> set[str]:\n"
        "    return {part for part in content.split() if part}\n"
        "\n"
        "def find_logged_segments(content: str) -> set[str]:\n"
        "    all_segments = find_bare_path_segments(content)\n"
        "    return all_segments\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A body with an intermediate binding is not a single pass-through, got: {issues!r}"
    )


def test_should_not_flag_function_that_drops_keyword_only_parameter() -> None:
    source = (
        "def target(first: int) -> int:\n"
        "    return first\n"
        "\n"
        "def alias(first: int, *, second: int) -> int:\n"
        "    return target(first)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Dropping a keyword-only parameter changes behavior, not a pure alias, got: {issues!r}"
    )


def test_should_not_flag_function_that_drops_var_positional_parameter() -> None:
    source = (
        "def target(first: int) -> int:\n"
        "    return first\n"
        "\n"
        "def alias(first: int, *rest: int) -> int:\n"
        "    return target(first)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Dropping *args changes behavior, not a pure alias, got: {issues!r}"
    )


def test_should_not_flag_function_that_drops_var_keyword_parameter() -> None:
    source = (
        "def target(first: int) -> int:\n"
        "    return first\n"
        "\n"
        "def alias(first: int, **rest: int) -> int:\n"
        "    return target(first)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Dropping **kwargs changes behavior, not a pure alias, got: {issues!r}"
    )


def test_should_skip_test_file() -> None:
    source = (
        "def find_bare_path_segments(content: str) -> set[str]:\n"
        "    return {part for part in content.split() if part}\n"
        "\n"
        "def find_bare_index_segments(content: str) -> set[str]:\n"
        "    return find_bare_path_segments(content)\n"
    )
    issues = check_zero_payload_function_alias(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_config_file() -> None:
    source = (
        "def find_bare_path_segments(content: str) -> set[str]:\n"
        "    return {part for part in content.split() if part}\n"
        "\n"
        "def find_bare_index_segments(content: str) -> set[str]:\n"
        "    return find_bare_path_segments(content)\n"
    )
    issues = check_zero_payload_function_alias(source, CONFIG_FILE_PATH)
    assert issues == [], f"config/ files exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_zero_payload_function_alias("def broken(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_should_not_flag_empty_file() -> None:
    issues = check_zero_payload_function_alias("", PRODUCTION_FILE_PATH)
    assert issues == [], f"Empty file must not be flagged, got: {issues!r}"


def test_should_not_flag_recursive_self_call() -> None:
    source = (
        "def walk(node: int) -> int:\n"
        "    return walk(node)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A self-call is recursion, not a zero-payload alias, got: {issues!r}"
    )


def test_should_flag_through_validate_content_for_hook_file() -> None:
    source = (
        "def find_bare_path_segments(content: str) -> set[str]:\n"
        "    return {part for part in content.split() if part}\n"
        "\n"
        "def find_bare_index_segments(content: str) -> set[str]:\n"
        "    return find_bare_path_segments(content)\n"
    )
    issues = code_rules_enforcer.validate_content(source, HOOK_INFRASTRUCTURE_PATH)
    assert any("find_bare_index_segments" in each for each in issues), (
        f"validate_content must surface the alias for hook files, got: {issues!r}"
    )


def test_should_not_flag_property_decorated_forwarder() -> None:
    source = (
        "def compute_total(amount: int) -> int:\n"
        "    return amount * 2\n"
        "\n"
        "class Cart:\n"
        "    @property\n"
        "    def total(self, amount: int) -> int:\n"
        "        return compute_total(amount)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A @property forwarder gains attribute semantics, not a zero-payload alias, got: {issues!r}"
    )


def test_should_not_flag_lru_cache_decorated_forwarder() -> None:
    source = (
        "import functools\n"
        "\n"
        "def lookup(key: int) -> int:\n"
        "    return key\n"
        "\n"
        "@functools.lru_cache\n"
        "def cached_lookup(key: int) -> int:\n"
        "    return lookup(key)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"An @lru_cache forwarder adds memoization the target lacks, got: {issues!r}"
    )


def test_should_not_flag_forwarder_that_adds_a_default_value() -> None:
    source = (
        "def target(first: int, second: int) -> int:\n"
        "    return first + second\n"
        "\n"
        "def alias(first: int, second: int = 5) -> int:\n"
        "    return target(first, second)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A default value makes a call shape valid that the target rejects, got: {issues!r}"
    )


def test_should_flag_async_pass_through_alias() -> None:
    source = (
        "async def real(value: int) -> int:\n"
        "    return value\n"
        "\n"
        "async def alias(value: int) -> int:\n"
        "    return real(value)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert any("alias" in each for each in issues), (
        f"An async pass-through alias must be flagged like its sync twin, got: {issues!r}"
    )


def test_should_not_flag_sync_alias_to_async_target() -> None:
    source = (
        "async def target(first: int) -> int:\n"
        "    return first\n"
        "\n"
        "def alias(first: int) -> int:\n"
        "    return target(first)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A sync alias to an async target returns a coroutine, changing the contract, got: {issues!r}"
    )


def test_should_not_flag_async_alias_to_sync_target() -> None:
    source = (
        "def target(first: int) -> int:\n"
        "    return first\n"
        "\n"
        "async def alias(first: int) -> int:\n"
        "    return target(first)\n"
    )
    issues = check_zero_payload_function_alias(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"An async alias to a sync target changes the awaitability contract, got: {issues!r}"
    )
