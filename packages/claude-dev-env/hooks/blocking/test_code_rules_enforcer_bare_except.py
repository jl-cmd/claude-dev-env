"""Tests for check_bare_except — flags except: / except Exception: / except BaseException:.

Per Plan 1c.bare_except_detector / Phase B4: bare exceptions swallow every
error including KeyboardInterrupt and SystemExit. They hide bugs and make
debugging impossible. Production code names the specific exception class
it intends to catch.
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


def check_bare_except(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_bare_except(content, file_path)


PRODUCTION_FILE_PATH = "/project/src/services.py"
TEST_FILE_PATH = "/project/src/test_services.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def test_should_flag_bare_except() -> None:
    source = "def fetch():\n    try:\n        do_thing()\n    except:\n        pass\n"
    issues = check_bare_except(source, PRODUCTION_FILE_PATH)
    assert any("bare except" in each.lower() for each in issues), (
        f"Expected bare except: flagged, got: {issues!r}"
    )


def test_should_flag_except_exception() -> None:
    source = (
        "def fetch():\n"
        "    try:\n"
        "        do_thing()\n"
        "    except Exception:\n"
        "        pass\n"
    )
    issues = check_bare_except(source, PRODUCTION_FILE_PATH)
    assert any("Exception" in each for each in issues), (
        f"Expected 'except Exception:' flagged, got: {issues!r}"
    )


def test_should_flag_except_base_exception() -> None:
    source = (
        "def fetch():\n"
        "    try:\n"
        "        do_thing()\n"
        "    except BaseException:\n"
        "        pass\n"
    )
    issues = check_bare_except(source, PRODUCTION_FILE_PATH)
    assert any("BaseException" in each for each in issues), (
        f"Expected 'except BaseException:' flagged, got: {issues!r}"
    )


def test_should_not_flag_specific_exception() -> None:
    source = (
        "def fetch():\n"
        "    try:\n"
        "        do_thing()\n"
        "    except ValueError:\n"
        "        pass\n"
    )
    issues = check_bare_except(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Specific exception must not be flagged, got: {issues!r}"


def test_should_not_flag_tuple_of_exceptions() -> None:
    source = (
        "def fetch():\n"
        "    try:\n"
        "        do_thing()\n"
        "    except (ValueError, KeyError):\n"
        "        pass\n"
    )
    issues = check_bare_except(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Tuple of exceptions must not be flagged, got: {issues!r}"


def test_should_skip_test_file() -> None:
    source = "try:\n    do_thing()\nexcept:\n    pass\n"
    issues = check_bare_except(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    source = "try:\n    do_thing()\nexcept:\n    pass\n"
    issues = check_bare_except(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    source = "try:\n  do(\n"
    issues = check_bare_except(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_should_include_line_number() -> None:
    source = "def fetch():\n    try:\n        do_thing()\n    except:\n        pass\n"
    issues = check_bare_except(source, PRODUCTION_FILE_PATH)
    assert len(issues) >= 1
    assert "Line 4" in issues[0], f"Issue must include line number, got: {issues[0]!r}"
