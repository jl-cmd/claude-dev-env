"""Tests for the printf-token check on str.format-logger (automation_logging) calls."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ENFORCER_FILENAME = "code_rules_enforcer.py"
ENFORCER_MODULE_NAME = "code_rules_enforcer_printf_under_test"
PRODUCTION_FILE_PATH = "shared_utils/web_automation/sample.py"
TEST_FILE_PATH = "shared_utils/web_automation/tests/test_sample.py"
FORMAT_LOGGER_IMPORT = (
    "from shared_utils.automation_logging import log_error, log_info, log_debug\n"
)


def load_enforcer_module() -> ModuleType:
    enforcer_path = Path(__file__).parent / ENFORCER_FILENAME
    module_spec = importlib.util.spec_from_file_location(ENFORCER_MODULE_NAME, enforcer_path)
    assert module_spec is not None
    assert module_spec.loader is not None
    enforcer_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(enforcer_module)
    return enforcer_module


enforcer = load_enforcer_module()


def test_should_flag_percent_s_in_format_logger_call() -> None:
    source = FORMAT_LOGGER_IMPORT + 'log_error("Skipping %s after error: %s", name, err)\n'
    issues = enforcer.check_logging_printf_tokens(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "printf token" in issues[0]


def test_should_flag_percent_d_in_format_logger_call() -> None:
    source = FORMAT_LOGGER_IMPORT + 'log_debug("attempt %d of %d", index, total)\n'
    issues = enforcer.check_logging_printf_tokens(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 1


def test_should_allow_brace_placeholders_in_format_logger_call() -> None:
    source = FORMAT_LOGGER_IMPORT + 'log_info("Processing {} of {}", index, total)\n'
    issues = enforcer.check_logging_printf_tokens(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_ignore_percent_token_without_format_logger_import() -> None:
    source = 'log_error("Skipping %s", name)\n'
    issues = enforcer.check_logging_printf_tokens(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_ignore_attribute_style_logger_call() -> None:
    source = FORMAT_LOGGER_IMPORT + 'logger.info("delivered %s", message_id)\n'
    issues = enforcer.check_logging_printf_tokens(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_inspect_message_literal_not_argument_value() -> None:
    source = FORMAT_LOGGER_IMPORT + 'log_info("status: {}", "100%s done")\n'
    issues = enforcer.check_logging_printf_tokens(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_exempt_test_files() -> None:
    source = FORMAT_LOGGER_IMPORT + 'log_error("Skipping %s", name)\n'
    issues = enforcer.check_logging_printf_tokens(source, TEST_FILE_PATH)
    assert issues == []


def test_should_resolve_aliased_format_logger_import() -> None:
    source = (
        "from shared_utils.automation_logging import log_error as report_error\n"
        + 'report_error("failed %s", name)\n'
    )
    issues = enforcer.check_logging_printf_tokens(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
