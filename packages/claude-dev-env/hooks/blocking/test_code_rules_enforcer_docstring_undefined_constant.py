"""Tests for check_docstring_names_undefined_constant — docstring-vs-impl drift.

A docstring that names an UPPER_SNAKE_CASE symbol as a contract identifier while
the enclosing module neither defines nor imports that name is docstring drift:
a reader who trusts the docstring to name a real constant finds nothing. This is
the deterministic slice of Category O6 where the named symbol is structurally a
constant (all-caps, underscore-joined) and resolvable against the module's
defined-and-imported name set.
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


def check_docstring_names_undefined_constant(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_names_undefined_constant(content, file_path)


PRODUCTION_FILE_PATH = "/project/scripts/dispatch_registry.py"
TEST_FILE_PATH = "/project/scripts/test_dispatch_registry.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def test_flags_docstring_naming_constant_the_module_never_defines() -> None:
    content = (
        "class HostedHookEntry:\n"
        '    """A hosted hook entry.\n'
        "\n"
        "    Attributes:\n"
        "        native_module_name: The module exposes a function named\n"
        "            NATIVE_EVALUATE_FUNCTION_NAME taking the payload and returning a\n"
        "            deny-reason string or None.\n"
        '    """\n'
        "\n"
        "    native_module_name: str\n"
    )
    issues = check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "NATIVE_EVALUATE_FUNCTION_NAME" in issues[0]


def test_passes_when_the_named_constant_is_defined_at_module_scope() -> None:
    content = (
        "MAXIMUM_RETRIES = 3\n"
        "\n"
        "def fetch_with_retries(url: str) -> str:\n"
        '    """Retry the fetch.\n'
        "\n"
        "    The loop runs at most MAXIMUM_RETRIES times before giving up.\n"
        '    """\n'
        "    return url\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_the_named_constant_is_imported() -> None:
    content = (
        "from config.timing import MAXIMUM_RETRIES\n"
        "\n"
        "def fetch_with_retries(url: str) -> str:\n"
        '    """Retry the fetch up to MAXIMUM_RETRIES times."""\n'
        "    return url\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_the_named_constant_is_an_aliased_import() -> None:
    content = (
        "from config.timing import RETRY_BUDGET as MAXIMUM_RETRIES\n"
        "\n"
        "def fetch_with_retries(url: str) -> str:\n"
        '    """Retry the fetch up to MAXIMUM_RETRIES times."""\n'
        "    return url\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_module_docstring_names_a_defined_constant() -> None:
    content = '"""Module that runs at most MAXIMUM_RETRIES attempts."""\n\nMAXIMUM_RETRIES = 3\n'
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_flags_module_docstring_naming_undefined_constant() -> None:
    content = '"""Module that runs at most MAXIMUM_RETRIES attempts."""\n\nvalue_in_use = 3\n'
    issues = check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "MAXIMUM_RETRIES" in issues[0]


def test_ignores_http_acronym_and_short_all_caps_words() -> None:
    content = (
        "def send_request(url: str) -> str:\n"
        '    """Send an HTTP GET request and return the body as JSON."""\n'
        "    return url\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_ignores_dunder_names() -> None:
    content = (
        "def export_surface() -> None:\n"
        '    """Names listed in __all__ form the export surface."""\n'
        "    return None\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_test_files_are_exempt() -> None:
    content = (
        "class HostedHookEntry:\n"
        '    """The module exposes NATIVE_EVALUATE_FUNCTION_NAME."""\n'
        "\n"
        "    native_module_name: str\n"
    )
    assert check_docstring_names_undefined_constant(content, TEST_FILE_PATH) == []


def test_hook_infrastructure_is_exempt() -> None:
    content = (
        "class HostedHookEntry:\n"
        '    """The module exposes NATIVE_EVALUATE_FUNCTION_NAME."""\n'
        "\n"
        "    native_module_name: str\n"
    )
    assert check_docstring_names_undefined_constant(content, HOOK_INFRASTRUCTURE_PATH) == []
