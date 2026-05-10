"""Tests for check_test_branching_in_production — flags prod-vs-test branching.

Per Plan 1c.di_pattern_check / Phase B3: production code that branches on
TESTING / PYTEST_CURRENT_TEST / sys.argv == 'test' creates two parallel
implementations the wrong way. The correct pattern is dependency injection
(`_test_hooks.py` sibling) so production code is single-path and tests
override the dependency.
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


def check_test_branching_in_production(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_test_branching_in_production(content, file_path)


PRODUCTION_FILE_PATH = "/project/src/services.py"
TEST_FILE_PATH = "/project/src/test_services.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def test_should_flag_os_environ_get_testing_branch() -> None:
    source = (
        "import os\n"
        "def fetch_user():\n"
        "    if os.environ.get('TESTING'):\n"
        "        return None\n"
        "    return real_fetch()\n"
    )
    issues = check_test_branching_in_production(source, PRODUCTION_FILE_PATH)
    assert any("TESTING" in each for each in issues), (
        f"Expected TESTING env branch flagged, got: {issues!r}"
    )


def test_should_flag_pytest_current_test_branch() -> None:
    source = (
        "import os\n"
        "def fetch_user():\n"
        "    if 'PYTEST_CURRENT_TEST' in os.environ:\n"
        "        return None\n"
        "    return real_fetch()\n"
    )
    issues = check_test_branching_in_production(source, PRODUCTION_FILE_PATH)
    assert any("PYTEST_CURRENT_TEST" in each for each in issues), (
        f"Expected PYTEST_CURRENT_TEST branch flagged, got: {issues!r}"
    )


def test_should_flag_env_testing_check() -> None:
    source = (
        "import os\n"
        "TESTING_FLAG = os.environ.get('TESTING') == '1'\n"
        "def get_db():\n"
        "    if TESTING_FLAG:\n"
        "        return MockDB()\n"
        "    return RealDB()\n"
    )
    issues = check_test_branching_in_production(source, PRODUCTION_FILE_PATH)
    assert any("TESTING" in each for each in issues), (
        f"Expected TESTING env access flagged, got: {issues!r}"
    )


def test_should_flag_environ_subscript_testing() -> None:
    source = (
        "import os\n"
        "def get_db():\n"
        "    if os.environ['TESTING']:\n"
        "        return None\n"
        "    return RealDB()\n"
    )
    issues = check_test_branching_in_production(source, PRODUCTION_FILE_PATH)
    assert any("TESTING" in each for each in issues), (
        f"Expected os.environ['TESTING'] flagged, got: {issues!r}"
    )


def test_should_not_flag_other_env_var_access() -> None:
    source = (
        "import os\n"
        "def get_db():\n"
        "    db_url = os.environ.get('DATABASE_URL')\n"
        "    return RealDB(db_url)\n"
    )
    issues = check_test_branching_in_production(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Non-test env vars must not trigger, got: {issues!r}"


def test_should_skip_test_file() -> None:
    source = (
        "import os\n"
        "def fetch_user():\n"
        "    if os.environ.get('TESTING'):\n"
        "        return None\n"
    )
    issues = check_test_branching_in_production(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    source = (
        "import os\n"
        "def fetch_user():\n"
        "    if os.environ.get('TESTING'):\n"
        "        return None\n"
    )
    issues = check_test_branching_in_production(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    source = "def fetch_user(\n"
    issues = check_test_branching_in_production(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_should_include_line_number_in_issue() -> None:
    source = (
        "import os\n\ndef fetch():\n    if os.environ.get('TESTING'):\n        pass\n"
    )
    issues = check_test_branching_in_production(source, PRODUCTION_FILE_PATH)
    assert len(issues) >= 1
    assert any("Line 4" in each for each in issues), (
        f"Issue must include line number, got: {issues!r}"
    )
