"""Tests for vacuous cleanup-on-failure assertion detection.

A cleanup-on-failure test that asserts no leftover temp file is left behind,
yet never proves the temp file was created, passes vacuously: the assertion
holds even when the on-failure cleanup is entirely broken. The gate flags that
shape so the author arranges a post-creation failure and asserts real removal.
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

TEST_FILE_PATH = "packages/app/tests/test_archive_rewrite.py"
PRODUCTION_FILE_PATH = "packages/app/services/archive_rewrite.py"


def test_should_flag_glob_emptiness_cleanup_test_without_temp_creation() -> None:
    source = (
        "def test_rewrite_removes_tmp_file_on_failure(tmp_path: Path) -> None:\n"
        "    stp_path = build_corrupt_stp(stp_path=tmp_path / 'corrupt.stp')\n"
        "    rewrite_properties_xml_atomically(stp_path=stp_path, patched='<x/>')\n"
        "    all_tmp_siblings = list(tmp_path.glob('*.tmp'))\n"
        "    assert len(all_tmp_siblings) == 0\n"
    )
    issues = code_rules_enforcer.check_vacuous_cleanup_assertion_tests(source, TEST_FILE_PATH)
    assert any("vacuous" in issue.lower() for issue in issues), (
        f"Expected a vacuous-cleanup issue, got: {issues}"
    )


def test_should_not_flag_when_post_creation_failure_is_arranged() -> None:
    source = (
        "def test_rewrite_removes_tmp_file_on_replace_failure(tmp_path, monkeypatch)"
        " -> None:\n"
        "    stp_path = build_valid_stp(stp_path=tmp_path / 'theme.stp')\n"
        "    monkeypatch.setattr(os, 'replace', _raise_oserror)\n"
        "    rewrite_properties_xml_atomically(stp_path=stp_path, patched='<x/>')\n"
        "    all_tmp_siblings = list(tmp_path.glob('*.tmp'))\n"
        "    assert len(all_tmp_siblings) == 0\n"
    )
    issues = code_rules_enforcer.check_vacuous_cleanup_assertion_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issue when failure is arranged, got: {issues}"


def test_should_not_flag_when_temp_existence_is_proven_first() -> None:
    source = (
        "def test_cleanup_removes_temp_on_failure(tmp_path: Path) -> None:\n"
        "    temporary_path = tmp_path / 'theme.stp.tmp'\n"
        "    temporary_path.write_bytes(b'partial')\n"
        "    assert temporary_path.exists()\n"
        "    run_cleanup_after_failure(temporary_path)\n"
        "    assert not list(tmp_path.glob('*.tmp'))\n"
    )
    issues = code_rules_enforcer.check_vacuous_cleanup_assertion_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issue when temp existence proven, got: {issues}"


def test_should_not_flag_success_named_cleanup_assertion() -> None:
    source = (
        "def test_rewrite_leaves_no_tmp_sibling_on_success(tmp_path: Path) -> None:\n"
        "    stp_path = build_valid_stp(stp_path=tmp_path / 'theme.stp')\n"
        "    rewrite_properties_xml_atomically(stp_path=stp_path, patched='<x/>')\n"
        "    all_tmp_siblings = list(tmp_path.glob('*.tmp'))\n"
        "    assert len(all_tmp_siblings) == 0\n"
    )
    issues = code_rules_enforcer.check_vacuous_cleanup_assertion_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issue for a success-named test, got: {issues}"


def test_should_not_flag_failure_test_asserting_real_behavior() -> None:
    source = (
        "def test_rewrite_reports_cleanup_failure_on_directory_tmp("
        "tmp_path: Path) -> None:\n"
        "    temporary_path = tmp_path / 'theme.stp.tmp'\n"
        "    temporary_path.mkdir()\n"
        "    write_outcome = rewrite_properties_xml_atomically("
        "stp_path=tmp_path / 't.stp', patched='<x/>')\n"
        "    assert write_outcome.temporary_cleanup_error_message is not None\n"
    )
    issues = code_rules_enforcer.check_vacuous_cleanup_assertion_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issue for a behavior assertion, got: {issues}"


def test_should_not_flag_mixed_assertion_cleanup_test() -> None:
    source = (
        "def test_rewrite_removes_tmp_and_reports_failure(tmp_path: Path) -> None:\n"
        "    stp_path = build_corrupt_stp(stp_path=tmp_path / 'corrupt.stp')\n"
        "    write_outcome = rewrite_properties_xml_atomically("
        "stp_path=stp_path, patched='<x/>')\n"
        "    assert write_outcome.is_write_successful is False\n"
        "    all_tmp_siblings = list(tmp_path.glob('*.tmp'))\n"
        "    assert len(all_tmp_siblings) == 0\n"
    )
    issues = code_rules_enforcer.check_vacuous_cleanup_assertion_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issue for a mixed-assertion test, got: {issues}"


def test_should_not_flag_in_production_files() -> None:
    source = (
        "def test_rewrite_removes_tmp_file_on_failure(tmp_path: Path) -> None:\n"
        "    all_tmp_siblings = list(tmp_path.glob('*.tmp'))\n"
        "    assert len(all_tmp_siblings) == 0\n"
    )
    issues = code_rules_enforcer.check_vacuous_cleanup_assertion_tests(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Expected no issue in a production file, got: {issues}"


def test_should_include_line_number_in_issue() -> None:
    source = (
        "def test_rewrite_removes_tmp_file_on_failure(tmp_path: Path) -> None:\n"
        "    all_tmp_siblings = list(tmp_path.glob('*.tmp'))\n"
        "    assert all_tmp_siblings == []\n"
    )
    issues = code_rules_enforcer.check_vacuous_cleanup_assertion_tests(source, TEST_FILE_PATH)
    assert any("Line 1" in issue for issue in issues), (
        f"Expected a line number in the issue, got: {issues}"
    )
