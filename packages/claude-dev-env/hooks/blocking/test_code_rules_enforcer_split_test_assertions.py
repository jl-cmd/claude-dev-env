"""Behavior tests for the code_rules_test_assertions code-rules check module."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_test_assertions import (  # noqa: E402
    check_constant_equality_tests,
    check_flag_gated_scenario_test_naming,
)

code_rules_enforcer = SimpleNamespace(
    check_constant_equality_tests=check_constant_equality_tests,
    check_flag_gated_scenario_test_naming=check_flag_gated_scenario_test_naming,
)


CONSTANT_EQUALITY_TEST_FILE_PATH = "packages/app/tests/test_constants.py"
SCENARIO_TEST_FILE_PATH = "packages/app/tests/test_submission_runner_loop.py"

_THREE_SIBLINGS_PATCH_THE_FLAG_ONE_SCENARIO_TEST_DOES_NOT = (
    "def test_should_submit_when_gate_passes(monkeypatch) -> None:\n"
    "    assert run() == 'submitted'\n"
    "\n"
    "def test_should_fail_when_reader_raises(monkeypatch) -> None:\n"
    "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
    "    assert run() == 'failed'\n"
    "\n"
    "def test_should_soft_skip_when_mismatch(monkeypatch) -> None:\n"
    "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
    "    assert run() == 'skipped'\n"
    "\n"
    "def test_should_hard_stop_when_unhealthy(monkeypatch) -> None:\n"
    "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
    "    assert run() == 'hard_stop'\n"
)


def test_should_not_flag_two_named_constants_compared_to_each_other() -> None:
    source = (
        "FOO = 'a'\n"
        "BAR = 'b'\n"
        "\n"
        "def test_constants_differ() -> None:\n"
        "    assert FOO == BAR\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(
        source, CONSTANT_EQUALITY_TEST_FILE_PATH
    )
    assert issues == [], (
        f"Expected no flag when both sides are named constants, got: {issues}"
    )


def test_should_flag_named_constant_compared_to_literal() -> None:
    source = (
        "FOO = 'a'\n"
        "\n"
        "def test_foo_value() -> None:\n"
        "    assert FOO == 'literal'\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(
        source, CONSTANT_EQUALITY_TEST_FILE_PATH
    )
    assert any("constant-value test" in issue for issue in issues), (
        f"Expected flag when UPPER_SNAKE compared to literal, got: {issues}"
    )


def test_should_advise_when_scenario_test_omits_flag_its_siblings_patch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code_rules_enforcer.check_flag_gated_scenario_test_naming(
        _THREE_SIBLINGS_PATCH_THE_FLAG_ONE_SCENARIO_TEST_DOES_NOT,
        SCENARIO_TEST_FILE_PATH,
    )
    advisory_text = capsys.readouterr().err
    assert "test_should_submit_when_gate_passes" in advisory_text, (
        f"Expected an advisory naming the un-patched scenario test, got: {advisory_text!r}"
    )
    assert "IS_STAGED_VERIFICATION_ENABLED" in advisory_text, (
        f"Expected the advisory to name the established flag, got: {advisory_text!r}"
    )


def test_should_stay_silent_when_scenario_test_patches_the_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = (
        "def test_should_submit_when_gate_passes(monkeypatch) -> None:\n"
        "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
        "    assert run() == 'submitted'\n"
        "\n"
        "def test_should_fail_when_reader_raises(monkeypatch) -> None:\n"
        "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
        "    assert run() == 'failed'\n"
    )
    code_rules_enforcer.check_flag_gated_scenario_test_naming(
        source, SCENARIO_TEST_FILE_PATH
    )
    advisory_text = capsys.readouterr().err
    assert advisory_text == "", (
        f"Expected silence when the scenario test patches the flag, got: {advisory_text!r}"
    )


def test_should_stay_silent_when_only_one_sibling_patches_the_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = (
        "def test_should_submit_when_gate_passes(monkeypatch) -> None:\n"
        "    assert run() == 'submitted'\n"
        "\n"
        "def test_should_fail_when_reader_raises(monkeypatch) -> None:\n"
        "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
        "    assert run() == 'failed'\n"
    )
    code_rules_enforcer.check_flag_gated_scenario_test_naming(
        source, SCENARIO_TEST_FILE_PATH
    )
    advisory_text = capsys.readouterr().err
    assert advisory_text == "", (
        f"One sibling patch is not an established flag; expected silence, got: {advisory_text!r}"
    )


def test_should_not_advise_for_production_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code_rules_enforcer.check_flag_gated_scenario_test_naming(
        _THREE_SIBLINGS_PATCH_THE_FLAG_ONE_SCENARIO_TEST_DOES_NOT,
        "packages/app/services/submission_pipeline.py",
    )
    advisory_text = capsys.readouterr().err
    assert advisory_text == "", (
        f"Production files are exempt; expected no advisory, got: {advisory_text!r}"
    )
