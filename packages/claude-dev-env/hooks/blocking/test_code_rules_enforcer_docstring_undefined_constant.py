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


def test_passes_when_token_is_attribute_on_an_imported_stdlib_module() -> None:
    content = (
        "import os\n"
        "def open_no_follow(target: str) -> int:\n"
        '    """Open target with O_NOFOLLOW so a symlink at target raises."""\n'
        "    return os.open(target, os.O_NOFOLLOW)\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_token_is_attribute_on_a_dotted_imported_module() -> None:
    content = (
        "import config.timing\n"
        "def delay() -> int:\n"
        '    """Sleep up to MAX_DELAY seconds."""\n'
        "    return config.timing.MAX_DELAY\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_token_is_an_environment_variable_string_key() -> None:
    content = (
        "import os\n"
        "def read_token() -> str:\n"
        '    """Read the secret from BWS_ACCESS_TOKEN in the environment."""\n'
        "    return os.environ['BWS_ACCESS_TOKEN']\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_token_is_a_naming_convention_descriptor() -> None:
    content = (
        "def is_styled(name: str) -> bool:\n"
        '    """Return True when name is UPPER_SNAKE_CASE styled."""\n'
        "    return name.isupper()\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_token_is_an_api_enum_string_literal() -> None:
    content = (
        "def submit_review(blocking: bool) -> dict[str, str]:\n"
        '    """Submit with event REQUEST_CHANGES when blocking."""\n'
        "    return {'event': 'REQUEST_CHANGES'} if blocking else {}\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_token_is_a_word_run_of_a_defined_or_imported_name() -> None:
    content = (
        "from github_constants import GITHUB_REVIEW_EVENT_REQUEST_CHANGES\n"
        "def submit_review() -> str:\n"
        '    """Submit with the REQUEST_CHANGES event."""\n'
        "    return GITHUB_REVIEW_EVENT_REQUEST_CHANGES\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_token_is_an_enum_family_sibling_of_an_imported_constant() -> None:
    content = (
        "from preflight_constants import MODE_STRICT\n"
        "def run(mode: str) -> None:\n"
        '    """mode: MODE_STRICT (autoconverge) or MODE_CLASSIFY (pr-converge)."""\n'
        "    if mode == MODE_STRICT:\n"
        "        return None\n"
        "    return None\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_docstring_frames_token_as_a_doc_file_reference() -> None:
    content = '"""Constants for code_rules_gate.py per CODE_RULES centralized-config rule."""\n\nMAX_VIOLATIONS = 3\n'
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_docstring_frames_token_with_a_file_suffix() -> None:
    content = (
        '"""Byte-copies CODE_RULES.md and TEST_QUALITY.md into the rules tree."""\n'
        "\n"
        "value_in_use = 3\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_docstring_frames_token_as_an_env_variable_set() -> None:
    content = (
        '"""Resolve the layout root.\n'
        "\n"
        "    If LLM_SETTINGS_ROOT is set to the repo root, uses that root.\n"
        '    """\n'
        "value_in_use = 3\n"
    )
    assert check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH) == []


def test_still_flags_the_genuine_miss_with_no_supporting_reference() -> None:
    content = (
        "class HostedHookEntry:\n"
        '    """A hosted hook entry.\n'
        "\n"
        "    Attributes:\n"
        "        native_module_name: The module exposes a function named\n"
        "            NATIVE_EVALUATE_FUNCTION_NAME taking the payload.\n"
        '    """\n'
        "\n"
        "    native_module_name: str\n"
    )
    issues = check_docstring_names_undefined_constant(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "NATIVE_EVALUATE_FUNCTION_NAME" in issues[0]
