"""Tests for check_docstring_args_match_signature — Args:-vs-signature drift.

A documented ``Args:`` entry naming a parameter the signature lacks is the
stale residue of a rename. Only the ``Args:`` section is validated; ``Raises:``
is left alone because callee-propagated exceptions cause false positives.
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


def check_docstring_args_match_signature(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_args_match_signature(content, file_path)


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/services.py"
TEST_FILE_PATH = "/project/src/test_services.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _function_with_stale_arg() -> str:
    return (
        "def fetch_user(account_id: int) -> str:\n"
        '    """Look up a user by id.\n'
        "\n"
        "    Args:\n"
        "        user_id: The user identifier.\n"
        "\n"
        "    Returns:\n"
        "        The user name.\n"
        '    """\n'
        "    lookup = _registry.get(account_id)\n"
        "    if not lookup:\n"
        "        return ''\n"
        "    return lookup.name\n"
    )


def test_should_flag_documented_arg_not_in_signature() -> None:
    issues = check_docstring_args_match_signature(_function_with_stale_arg(), PRODUCTION_FILE_PATH)
    assert any("user_id" in each for each in issues), (
        f"Expected stale 'user_id' flag, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_not_flag_when_args_match_signature() -> None:
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
        "        return ''\n"
        "    return lookup.name\n"
    )
    issues = check_docstring_args_match_signature(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Matching Args must not be flagged, got: {issues!r}"


def test_should_handle_parenthesized_type_in_arg_entry() -> None:
    source = (
        "def fetch_user(account_id: int) -> str:\n"
        '    """Look up a user by id.\n'
        "\n"
        "    Args:\n"
        "        user_id (int): The user identifier.\n"
        "\n"
        "    Returns:\n"
        "        The user name.\n"
        '    """\n'
        "    lookup = _registry.get(account_id)\n"
        "    if not lookup:\n"
        "        return ''\n"
        "    return lookup.name\n"
    )
    issues = check_docstring_args_match_signature(source, PRODUCTION_FILE_PATH)
    assert any("user_id" in each for each in issues), (
        f"Parenthesized-type entry must still be parsed, got: {issues!r}"
    )


def test_should_count_vararg_and_kwarg_as_real_parameters() -> None:
    source = (
        "def collect(first: int, *extra_values, **options) -> int:\n"
        '    """Collect values.\n'
        "\n"
        "    Args:\n"
        "        first: The leading value.\n"
        "        extra_values: Additional positional values.\n"
        "        options: Keyword overrides.\n"
        '    """\n'
        "    total = first\n"
        "    for each_value in extra_values:\n"
        "        total += each_value\n"
        "    return total\n"
    )
    issues = check_docstring_args_match_signature(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"vararg/kwarg must count as parameters, got: {issues!r}"


def test_should_not_flag_self_documented_when_method_uses_self() -> None:
    source = (
        "class Service:\n"
        "    def fetch(self, user_id: int) -> int:\n"
        '        """Fetch a record.\n'
        "\n"
        "        Args:\n"
        "            user_id: The user identifier.\n"
        '        """\n'
        "        record = self._registry.get(user_id)\n"
        "        if record is None:\n"
        "            return 0\n"
        "        return record\n"
    )
    issues = check_docstring_args_match_signature(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"self-using method must not be flagged, got: {issues!r}"


def test_should_stop_parsing_args_at_next_section() -> None:
    source = (
        "def fetch_user(user_id: int) -> str:\n"
        '    """Look up a user by id.\n'
        "\n"
        "    Args:\n"
        "        user_id: The user identifier.\n"
        "\n"
        "    Raises:\n"
        "        LookupError: When missing.\n"
        '    """\n'
        "    lookup = _registry.get(user_id)\n"
        "    if not lookup:\n"
        "        raise LookupError('missing')\n"
        "    return lookup.name\n"
    )
    issues = check_docstring_args_match_signature(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Raises entries past Args must be ignored, got: {issues!r}"


def test_should_skip_private_function() -> None:
    source = (
        "def _fetch(account_id: int) -> int:\n"
        '    """Fetch internally.\n'
        "\n"
        "    Args:\n"
        "        user_id: stale name.\n"
        '    """\n'
        "    value = _registry.get(account_id)\n"
        "    return value\n"
    )
    issues = check_docstring_args_match_signature(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Private functions exempt, got: {issues!r}"


def test_should_skip_short_function() -> None:
    source = (
        "def fetch(account_id: int) -> int:\n"
        '    """Args:\n'
        "        user_id: stale.\n"
        '    """\n'
        "    return account_id\n"
    )
    issues = check_docstring_args_match_signature(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Trivial-body functions exempt, got: {issues!r}"


def test_should_skip_test_file() -> None:
    issues = check_docstring_args_match_signature(_function_with_stale_arg(), TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_docstring_args_match_signature(
        _function_with_stale_arg(), HOOK_INFRASTRUCTURE_PATH
    )
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_docstring_args_match_signature("def fetch(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_validate_content_surfaces_args_drift() -> None:
    issues = validate_content(_function_with_stale_arg(), PRODUCTION_FILE_PATH, old_content="")
    matching_issues = [each for each in issues if "user_id" in each and "Args" in each]
    assert matching_issues, (
        f"Expected validate_content to surface the Args drift issue, got: {issues!r}"
    )


def test_should_not_flag_deeper_indented_continuation_line() -> None:
    source = (
        "def fetch_user(user_id: int) -> str:\n"
        '    """Look up a user by id.\n'
        "\n"
        "    Args:\n"
        "        user_id: The user identifier. Example mapping:\n"
        "            shadow_key: not a parameter.\n"
        "\n"
        "    Returns:\n"
        "        The user name.\n"
        '    """\n'
        "    lookup = _registry.get(user_id)\n"
        "    if not lookup:\n"
        "        return ''\n"
        "    return lookup.name\n"
    )
    issues = check_docstring_args_match_signature(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Continuation lines must not be parsed as args, got: {issues!r}"


def test_should_not_flag_documented_kwargs_keys() -> None:
    source = (
        "def configure(timeout: int, **overrides) -> None:\n"
        '    """Configure the client.\n'
        "\n"
        "    Args:\n"
        "        timeout: Seconds to wait.\n"
        "        max_retries: A documented keyword override.\n"
        "\n"
        "    Returns:\n"
        "        None.\n"
        '    """\n'
        "    settings = dict(overrides)\n"
        "    settings['timeout'] = timeout\n"
        "    return None\n"
    )
    issues = check_docstring_args_match_signature(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"**kwargs-key docs must not be flagged, got: {issues!r}"
