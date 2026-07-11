"""Tests for broadened logging f-string detection.

Covers attribute-style calls (logger.*, logging.*, log.*) alongside
the legacy snake_case helpers (log_info, log_error, ...).
"""

import importlib.util
from pathlib import Path
from types import ModuleType


ENFORCER_FILENAME = "code_rules_enforcer.py"
ENFORCER_MODULE_NAME = "code_rules_enforcer_under_test"


def load_enforcer_module() -> ModuleType:
    enforcer_path = Path(__file__).parent / ENFORCER_FILENAME
    module_spec = importlib.util.spec_from_file_location(
        ENFORCER_MODULE_NAME, enforcer_path
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    enforcer_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(enforcer_module)
    return enforcer_module


enforcer = load_enforcer_module()

FSTRING_OPENER = 'f"'
FSTRING_CLOSER = '"'


def build_fstring_call(call_prefix: str, body: str) -> str:
    return call_prefix + "(" + FSTRING_OPENER + body + FSTRING_CLOSER + ")\n"


def test_should_flag_logger_info_fstring() -> None:
    source = build_fstring_call("logger.info", "processing {item}")
    issues = enforcer.check_logging_fstrings(source)
    assert len(issues) == 1
    assert "f-string in log call" in issues[0]


def test_should_flag_logging_error_fstring() -> None:
    source = build_fstring_call("logging.error", "failed: {err}")
    issues = enforcer.check_logging_fstrings(source)
    assert len(issues) == 1


def test_should_flag_log_debug_fstring() -> None:
    source = build_fstring_call("log.debug", "value={x}")
    issues = enforcer.check_logging_fstrings(source)
    assert len(issues) == 1


def test_should_flag_logger_exception_fstring() -> None:
    source = build_fstring_call("logger.exception", "boom {e}")
    issues = enforcer.check_logging_fstrings(source)
    assert len(issues) == 1


def test_should_still_flag_log_info_snake_case() -> None:
    source = build_fstring_call("log_info", "legacy helper {value}")
    issues = enforcer.check_logging_fstrings(source)
    assert len(issues) == 1


def test_should_flag_log_exception_fstring() -> None:
    source = build_fstring_call("log_exception", "snake exception {e}")
    issues = enforcer.check_logging_fstrings(source)
    assert len(issues) == 1


def test_should_flag_uppercase_fstring_prefix() -> None:
    source = 'logger.info(F"uppercase {item}")\n'
    issues = enforcer.check_logging_fstrings(source)
    assert len(issues) == 1


def test_should_flag_raw_fstring_prefix_rf() -> None:
    source = 'logger.info(rf"raw path {path}")\n'
    issues = enforcer.check_logging_fstrings(source)
    assert len(issues) == 1


def test_should_flag_raw_fstring_prefix_fr() -> None:
    source = 'logger.info(fr"raw path {path}")\n'
    issues = enforcer.check_logging_fstrings(source)
    assert len(issues) == 1


def test_should_allow_logger_info_with_format_args() -> None:
    source = 'logger.info("processing %s", item)\n'
    issues = enforcer.check_logging_fstrings(source)
    assert issues == []


def test_should_allow_log_info_with_format_args() -> None:
    source = 'log_info("processing %s", item)\n'
    issues = enforcer.check_logging_fstrings(source)
    assert issues == []
