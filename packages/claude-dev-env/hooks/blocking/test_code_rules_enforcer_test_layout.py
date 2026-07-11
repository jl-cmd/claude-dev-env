from __future__ import annotations

import importlib.util
from pathlib import Path

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location("code_rules_enforcer", ENFORCER_PATH)
assert specification is not None and specification.loader is not None
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_FILE_PATH = "packages/app/services/report.py"
TEST_FILE_PATH = "packages/app/services/test_report.py"
UNDERSCORE_TEST_FILE_PATH = "packages/app/services/report_test.py"
CONFTEST_FILE_PATH = "packages/app/tests/conftest.py"
SHARED_TEST_MODULE_PATH = "packages/app/tests/expected_values.py"
TEST_CONSTANTS_MODULE_PATH = "packages/app/hooks_constants/test_layout_constants.py"
CONFIG_UNDER_TESTS_PATH = "packages/app/tests/config/timing.py"


def _dead_constant(source: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_dead_test_module_constant(source, file_path)

def _unused_parameter(source: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_unused_test_helper_parameter(source, file_path)

def test_should_flag_dead_private_constant_in_test_file() -> None:
    source = (
        "_ABSENT_DOTENV_FILENAME = 'absent.env'\n"
        "\n"
        "def test_reads_environment() -> None:\n"
        "    assert True\n"
    )
    issues = _dead_constant(source, TEST_FILE_PATH)
    assert any("_ABSENT_DOTENV_FILENAME" in each_issue for each_issue in issues), issues

def test_should_flag_dead_constant_in_underscore_test_module() -> None:
    source = (
        "_UNREAD_CONSTANT = 'x'\n"
        "\n"
        "def test_something() -> None:\n"
        "    assert True\n"
    )
    issues = _dead_constant(source, UNDERSCORE_TEST_FILE_PATH)
    assert any("_UNREAD_CONSTANT" in each_issue for each_issue in issues), issues

def test_should_not_flag_constant_read_by_a_later_line() -> None:
    source = (
        "_EXPECTED_TOTAL = 208\n"
        "\n"
        "def test_total_matches() -> None:\n"
        "    assert compute_total() == _EXPECTED_TOTAL\n"
    )
    assert _dead_constant(source, TEST_FILE_PATH) == []

def test_should_not_flag_dead_constant_in_production_file() -> None:
    source = "_UNUSED_CONSTANT = 'x'\n"
    assert _dead_constant(source, PRODUCTION_FILE_PATH) == []

def test_should_not_flag_shared_constant_in_conftest() -> None:
    source = (
        "SHARED_TIMEOUT_SECONDS = 30\n"
        "\n"
        "def _database() -> object:\n"
        "    return connect()\n"
    )
    assert _dead_constant(source, CONFTEST_FILE_PATH) == []

def test_should_not_flag_shared_constant_module_under_tests() -> None:
    source = "EXPECTED_TOTAL = 208\n"
    assert _dead_constant(source, SHARED_TEST_MODULE_PATH) == []

def test_should_not_flag_constant_in_a_constants_module() -> None:
    source = "SHARED_LAYOUT_LIMIT = 50\n"
    assert _dead_constant(source, TEST_CONSTANTS_MODULE_PATH) == []

def test_should_not_flag_constant_in_config_module_under_tests() -> None:
    source = "REQUEST_TIMEOUT_SECONDS = 30\n"
    assert _dead_constant(source, CONFIG_UNDER_TESTS_PATH) == []

def test_should_flag_unused_private_helper_parameter() -> None:
    source = "def _configuration(monkeypatch, tmp_path):\n    return build_config()\n"
    issues = _unused_parameter(source, TEST_FILE_PATH)
    flagged_parameters = {"monkeypatch", "tmp_path"}
    assert all(
        any(each_name in each_issue for each_issue in issues) for each_name in flagged_parameters
    ), issues

def test_should_not_flag_parameter_the_body_reads() -> None:
    source = "def _configuration(database_url):\n    return build_config(database_url)\n"
    assert _unused_parameter(source, TEST_FILE_PATH) == []

def test_should_not_flag_fixture_parameters() -> None:
    source = "import pytest\n\n@pytest.fixture\ndef _database(monkeypatch):\n    return connect()\n"
    assert _unused_parameter(source, TEST_FILE_PATH) == []

def test_should_not_flag_public_test_function_parameters() -> None:
    source = (
        "def test_writes_row(postgres_database_url) -> None:\n"
        "    assert postgres_database_url is not None\n"
    )
    assert _unused_parameter(source, TEST_FILE_PATH) == []
