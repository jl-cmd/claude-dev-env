"""Specifications for the quality gate reaching every PowerShell suite.

A suite nobody calls stops guarding without failing, so the tree reads as
covered while nothing holds it. These tests pin the wiring that calls the
suites and the directory the call points at.
"""

from __future__ import annotations

from pathlib import Path

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
_CHECK_SCRIPT_PATH = _SCRIPTS_DIRECTORY / "check.ps1"
_RUNNER_SCRIPT_PATH = _SCRIPTS_DIRECTORY / "Invoke-PesterSuites.ps1"
_TESTS_DIRECTORY = _SCRIPTS_DIRECTORY / "tests"
_SUITE_GLOB = "*.Tests.ps1"
_UTF8_ENCODING = "utf-8"


def test_should_run_the_suites_as_a_gate_tool() -> None:
    script_text = _CHECK_SCRIPT_PATH.read_text(encoding=_UTF8_ENCODING)

    assert "Invoke-Tool -Label 'pester'" in script_text
    assert "Invoke-PesterSuites.ps1" in script_text
    assert "SkipPester" in script_text


def test_should_point_the_run_at_the_directory_holding_the_suites() -> None:
    script_text = _CHECK_SCRIPT_PATH.read_text(encoding=_UTF8_ENCODING)

    assert "$pesterTestsRoot = Resolve-Path (Join-Path $PSScriptRoot 'tests')" in (
        script_text
    )
    assert "-TestsRoot $pesterTestsRoot" in script_text
    assert list(_TESTS_DIRECTORY.glob(_SUITE_GLOB))


def test_should_run_the_suites_in_a_child_process() -> None:
    """Invoke-Tool reads an exit code, which an in-process cmdlet never sets."""
    script_text = _CHECK_SCRIPT_PATH.read_text(encoding=_UTF8_ENCODING)

    assert "pwsh -NoProfile -File" in script_text
    assert "Invoke-Pester -Configuration" not in script_text
    assert "Invoke-Pester -Configuration" in (
        _RUNNER_SCRIPT_PATH.read_text(encoding=_UTF8_ENCODING)
    )


def test_should_fail_the_run_when_the_module_is_missing() -> None:
    runner_text = _RUNNER_SCRIPT_PATH.read_text(encoding=_UTF8_ENCODING)

    assert "Get-Module -ListAvailable -Name Pester" in runner_text
    assert "exit 1" in runner_text
