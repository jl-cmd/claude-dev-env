"""Tests for check_logging_adjacent_string_literals."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ENFORCER_FILENAME = "code_rules_enforcer.py"
ENFORCER_MODULE_NAME = "code_rules_enforcer_adjacent_literals_tests"
PRODUCTION_FILE_PATH = "shared_utils/web_automation/sample.py"
TEST_FILE_PATH = "shared_utils/web_automation/tests/test_sample.py"


def load_enforcer_module() -> ModuleType:
    loader_path = Path(__file__).parent / ENFORCER_FILENAME
    module_spec = importlib.util.spec_from_file_location(ENFORCER_MODULE_NAME, loader_path)
    assert module_spec is not None
    assert module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


enforcer = load_enforcer_module()


def test_should_flag_adjacent_literals_in_attribute_logger_call() -> None:
    source = 'logger.info("[Batch]" " Failed %s", job_name)\n'
    issues = enforcer.check_logging_adjacent_string_literals(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "adjacent string literals" in issues[0]


def test_should_flag_adjacent_literals_in_log_helper_call() -> None:
    source = 'log_debug("[Batch]" " Completed {}", job_name)\n'
    issues = enforcer.check_logging_adjacent_string_literals(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 1


def test_should_flag_adjacent_literals_on_underscore_prefixed_logger() -> None:
    source = '_logger.info("[Batch]" " Failed %s", job_name)\n'
    issues = enforcer.check_logging_adjacent_string_literals(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "adjacent string literals" in issues[0]


def test_should_flag_adjacent_single_quoted_literals() -> None:
    source = "logger.warning('[Batch]' ' Skipped %s', job_name)\n"
    issues = enforcer.check_logging_adjacent_string_literals(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 1


def test_should_allow_single_literal_log_call() -> None:
    source = 'logger.info("[Batch] Starting %s (row %d)", job_name, attempt_index)\n'
    issues = enforcer.check_logging_adjacent_string_literals(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_comma_separated_string_arguments() -> None:
    source = 'logger.info("delivered %s %s", message_id, "queued")\n'
    issues = enforcer.check_logging_adjacent_string_literals(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_explicit_plus_concatenation() -> None:
    source = 'logger.info("[Batch] " + suffix_pattern, job_name)\n'
    issues = enforcer.check_logging_adjacent_string_literals(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_adjacent_literals_outside_log_calls() -> None:
    source = 'banner_text = "[Batch]" " Failed %s"\n'
    issues = enforcer.check_logging_adjacent_string_literals(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_exempt_test_files() -> None:
    source = 'logger.info("[Batch]" " Failed %s", job_name)\n'
    issues = enforcer.check_logging_adjacent_string_literals(source, TEST_FILE_PATH)
    assert issues == []


def test_should_skip_non_python_files() -> None:
    source = 'logger.info("[Batch]" " Failed %s", job_name)\n'
    issues = enforcer.check_logging_adjacent_string_literals(source, "notes.md")
    assert issues == []
