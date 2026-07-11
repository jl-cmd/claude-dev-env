"""Tests for check_boundary_types — flags Any at module boundaries.

Per Plan 1c.boundary_type_check / Phase B6: a function signature or class
attribute typed with `Any` (directly or nested inside a generic) makes
no type promise to callers. Production code at boundaries should name
the concrete shape it accepts and returns. Local variables are exempt
(they are private to the function); `if TYPE_CHECKING:` blocks are
exempt (those imports never reach runtime); `protocols.py` and
`types.py` are exempt (interface declaration files).
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


def check_boundary_types(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_boundary_types(content, file_path)


PRODUCTION_FILE_PATH = "/project/src/services.py"
PROTOCOLS_FILE_PATH = "/project/src/protocols.py"
TYPES_FILE_PATH = "/project/src/types.py"
TEST_FILE_PATH = "/project/src/test_services.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def test_should_flag_any_as_direct_param_annotation() -> None:
    source = (
        "from typing import Any\n\ndef fetch(payload: Any) -> None:\n    return None\n"
    )
    issues = check_boundary_types(source, PRODUCTION_FILE_PATH)
    assert any("Any" in each for each in issues), (
        f"Expected Any-in-signature flag, got: {issues!r}"
    )


def test_should_flag_any_in_dict_param() -> None:
    source = (
        "from typing import Any\n"
        "\n"
        "def fetch(payload: dict[str, Any]) -> None:\n"
        "    return None\n"
    )
    issues = check_boundary_types(source, PRODUCTION_FILE_PATH)
    assert any("Any" in each for each in issues), (
        f"Expected dict[str, Any] flagged, got: {issues!r}"
    )


def test_should_flag_any_as_return_type() -> None:
    source = (
        "from typing import Any, List\n\ndef fetch() -> List[Any]:\n    return []\n"
    )
    issues = check_boundary_types(source, PRODUCTION_FILE_PATH)
    assert any("Any" in each for each in issues), (
        f"Expected List[Any] return flagged, got: {issues!r}"
    )


def test_should_flag_any_nested_two_levels() -> None:
    source = (
        "from typing import Any\n"
        "\n"
        "def fetch(payload: dict[str, list[Any]]) -> None:\n"
        "    return None\n"
    )
    issues = check_boundary_types(source, PRODUCTION_FILE_PATH)
    assert any("Any" in each for each in issues), (
        f"Expected nested Any flagged, got: {issues!r}"
    )


def test_should_flag_callable_returning_any() -> None:
    source = (
        "from typing import Any, Callable\n"
        "\n"
        "def fetch() -> Callable[..., Any]:\n"
        "    return lambda: 1\n"
    )
    issues = check_boundary_types(source, PRODUCTION_FILE_PATH)
    assert any("Any" in each for each in issues), (
        f"Expected Callable[..., Any] flagged, got: {issues!r}"
    )


def test_should_flag_any_in_class_attribute_annotation() -> None:
    source = "from typing import Any\n\nclass Cache:\n    storage: dict[str, Any]\n"
    issues = check_boundary_types(source, PRODUCTION_FILE_PATH)
    assert any("Any" in each for each in issues), (
        f"Expected class-attribute Any flagged, got: {issues!r}"
    )


def test_should_not_flag_specific_dict_value_type() -> None:
    source = "def fetch(payload: dict[str, int]) -> dict[str, str]:\n    return {}\n"
    issues = check_boundary_types(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Specific types must not be flagged, got: {issues!r}"


def test_should_not_flag_local_variable_annotation() -> None:
    source = (
        "from typing import Any\n"
        "\n"
        "def fetch() -> None:\n"
        "    cache: dict[str, Any] = {}\n"
        "    return None\n"
    )
    issues = check_boundary_types(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Local var annotations must not be flagged, got: {issues!r}"


def test_should_skip_protocols_file() -> None:
    source = (
        "from typing import Any, Protocol\n"
        "\n"
        "class Storage(Protocol):\n"
        "    def get(self, key: str) -> Any: ...\n"
    )
    issues = check_boundary_types(source, PROTOCOLS_FILE_PATH)
    assert issues == [], f"protocols.py exempt, got: {issues!r}"


def test_should_skip_types_file() -> None:
    source = (
        "from typing import Any\n\ndef coerce(value: Any) -> Any:\n    return value\n"
    )
    issues = check_boundary_types(source, TYPES_FILE_PATH)
    assert issues == [], f"types.py exempt, got: {issues!r}"


def test_should_skip_test_file() -> None:
    source = (
        "from typing import Any\n\ndef fetch(payload: Any) -> None:\n    return None\n"
    )
    issues = check_boundary_types(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    source = (
        "from typing import Any\n\ndef fetch(payload: Any) -> None:\n    return None\n"
    )
    issues = check_boundary_types(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    source = "def fetch(\n"
    issues = check_boundary_types(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_should_include_line_number() -> None:
    source = (
        "from typing import Any\n\ndef fetch(payload: Any) -> None:\n    return None\n"
    )
    issues = check_boundary_types(source, PRODUCTION_FILE_PATH)
    assert len(issues) >= 1
    assert "Line 3" in issues[0], f"Issue must include line number, got: {issues[0]!r}"
