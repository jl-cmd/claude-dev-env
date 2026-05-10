"""Tests for check_docstring_format — Google-style Args:/Returns:/Raises:.

Per Plan 1c.docstring_format_check / Phase B7: a public function whose
signature takes parameters, returns a non-None value, or raises an
exception must document those facts in Google-style sections so
callers can reason about the contract without reading the body.

Exemptions: private (`_foo`), dunder (`__init__`), `@property`,
functions ≤3 lines (trivial), abstract methods, test files.
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


def check_docstring_format(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_format(content, file_path)


PRODUCTION_FILE_PATH = "/project/src/services.py"
TEST_FILE_PATH = "/project/src/test_services.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _function_with_param_no_docstring() -> str:
    return (
        "def fetch_user(user_id: int) -> str:\n"
        "    lookup = _registry.get(user_id)\n"
        "    if not lookup:\n"
        "        return ''\n"
        "    return lookup.name\n"
    )


def test_should_flag_public_function_with_params_missing_args_section() -> None:
    issues = check_docstring_format(
        _function_with_param_no_docstring(), PRODUCTION_FILE_PATH
    )
    assert any("Args" in each for each in issues), (
        f"Expected missing-Args flag, got: {issues!r}"
    )


def test_should_flag_public_function_with_non_none_return_missing_returns_section() -> (
    None
):
    source = (
        "def fetch_user(user_id: int) -> str:\n"
        '    """Look up a user by id.\n'
        "\n"
        "    Args:\n"
        "        user_id: The user identifier.\n"
        '    """\n'
        "    lookup = _registry.get(user_id)\n"
        "    if not lookup:\n"
        "        return ''\n"
        "    return lookup.name\n"
    )
    issues = check_docstring_format(source, PRODUCTION_FILE_PATH)
    assert any("Returns" in each or "Yields" in each for each in issues), (
        f"Expected missing-Returns flag, got: {issues!r}"
    )


def test_should_flag_public_function_with_raise_missing_raises_section() -> None:
    source = (
        "def fetch_user(user_id: int) -> str:\n"
        '    """Look up a user by id.\n'
        "\n"
        "    Args:\n"
        "        user_id: The user identifier.\n"
        "\n"
        "    Returns:\n"
        "        The user name.\n"
        '    """\n'
        "    lookup = _registry.get(user_id)\n"
        "    if not lookup:\n"
        "        raise LookupError('missing')\n"
        "    return lookup.name\n"
    )
    issues = check_docstring_format(source, PRODUCTION_FILE_PATH)
    assert any("Raises" in each for each in issues), (
        f"Expected missing-Raises flag, got: {issues!r}"
    )


def test_should_not_flag_function_with_complete_google_docstring() -> None:
    source = (
        "def fetch_user(user_id: int) -> str:\n"
        '    """Look up a user by id.\n'
        "\n"
        "    Args:\n"
        "        user_id: The user identifier.\n"
        "\n"
        "    Returns:\n"
        "        The user name.\n"
        "\n"
        "    Raises:\n"
        "        LookupError: When the user is missing.\n"
        '    """\n'
        "    lookup = _registry.get(user_id)\n"
        "    if not lookup:\n"
        "        raise LookupError('missing')\n"
        "    return lookup.name\n"
    )
    issues = check_docstring_format(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Complete docstring must not be flagged, got: {issues!r}"


def test_should_not_require_returns_when_return_type_is_none() -> None:
    source = (
        "def store_user(user_id: int) -> None:\n"
        '    """Persist a user record.\n'
        "\n"
        "    Args:\n"
        "        user_id: The user identifier.\n"
        '    """\n'
        "    if user_id < 0:\n"
        "        return\n"
        "    _registry[user_id] = True\n"
    )
    issues = check_docstring_format(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"None-returning function must not require Returns:, got: {issues!r}"
    )


def test_should_accept_yields_in_lieu_of_returns_for_generator() -> None:
    source = (
        'def stream_users(batch_size: int) -> "Iterator[str]":\n'
        '    """Stream user names lazily.\n'
        "\n"
        "    Args:\n"
        "        batch_size: How many to read at a time.\n"
        "\n"
        "    Yields:\n"
        "        Each user name in turn.\n"
        '    """\n'
        "    for each in _registry.values():\n"
        "        yield each.name\n"
    )
    issues = check_docstring_format(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Yields: must satisfy Returns: requirement, got: {issues!r}"


def test_should_skip_private_function() -> None:
    source = "def _internal_helper(value: int) -> int:\n    return value * 2\n"
    issues = check_docstring_format(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Private functions exempt, got: {issues!r}"


def test_should_skip_dunder_method() -> None:
    source = (
        "class Cache:\n"
        "    def __init__(self, capacity: int) -> None:\n"
        "        self._capacity = capacity\n"
        "        self._storage = {}\n"
        "        self._hits = 0\n"
        "        self._misses = 0\n"
    )
    issues = check_docstring_format(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Dunder methods exempt, got: {issues!r}"


def test_should_skip_property_method() -> None:
    source = (
        "class Cache:\n"
        "    @property\n"
        "    def capacity(self) -> int:\n"
        "        first_calculation = self._capacity\n"
        "        adjusted = first_calculation - self._reserved\n"
        "        return adjusted\n"
    )
    issues = check_docstring_format(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"@property methods exempt, got: {issues!r}"


def test_should_skip_short_function() -> None:
    source = "def double(value: int) -> int:\n    return value * 2\n"
    issues = check_docstring_format(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Functions <=3 lines exempt, got: {issues!r}"


def test_should_skip_abstract_method() -> None:
    source = (
        "from abc import abstractmethod\n"
        "\n"
        "class Repository:\n"
        "    @abstractmethod\n"
        "    def fetch(self, key: str) -> int:\n"
        "        ...\n"
    )
    issues = check_docstring_format(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"@abstractmethod exempt, got: {issues!r}"


def test_should_skip_test_file() -> None:
    issues = check_docstring_format(_function_with_param_no_docstring(), TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_docstring_format(
        _function_with_param_no_docstring(), HOOK_INFRASTRUCTURE_PATH
    )
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_docstring_format("def fetch(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_should_not_count_self_or_cls_as_documentable_params() -> None:
    source = (
        "class Cache:\n"
        "    def reset(self) -> None:\n"
        '        """Drop all cached entries."""\n'
        "        self._storage.clear()\n"
        "        self._hits = 0\n"
        "        self._misses = 0\n"
    )
    issues = check_docstring_format(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"self-only methods must not require Args:, got: {issues!r}"
