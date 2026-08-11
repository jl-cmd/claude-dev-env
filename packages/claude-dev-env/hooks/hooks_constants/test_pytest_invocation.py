"""Recognize and allow fixtures for pytest_invocation segment classification."""

from __future__ import annotations

import pytest

from hooks_constants.pytest_invocation import (
    segment_reports_a_pytest_exit_code,
    segment_runs_pytest,
)
from hooks_constants.shell_command_pipeline import pipeline_segments_for_command


def _first_segment_tokens(command: str) -> list[str]:
    all_pairs = pipeline_segments_for_command(command)
    assert all_pairs, f"expected at least one segment for {command!r}"
    return all_pairs[0][0]


@pytest.mark.parametrize(
    "all_segment_tokens",
    [
        ["pytest", "tests"],
        ["pytest.exe", "tests"],
        ["pytest.bat", "tests"],
        ["py.test", "tests"],
        ["python", "-m", "pytest"],
        ["python", "-mpytest"],
        ["python3", "-m", "pytest", "tests"],
        ["pythonw", "-m", "pytest"],
        ["pypy3", "-m", "pytest", "tests"],
        ["pypy3", "--jit", "off", "-m", "pytest"],
        ["py", "-3", "-m", "pytest"],
        [r"C:\Python313\python.exe", "-m", "pytest"],
        ["time", "pytest", "tests"],
        ["sudo", "pytest", "tests"],
        ["sudo", "-u", "ci", "pytest", "tests"],
        ["sudo", "-nu", "ci", "pytest", "tests"],
        ["uv", "run", "pytest", "tests"],
        ["uv", "run", "--frozen", "pytest", "tests"],
        ["uv", "tool", "run", "pytest", "tests"],
        ["uvx", "pytest", "tests"],
        ["poetry", "run", "pytest", "tests"],
        ["pipenv", "run", "pytest", "tests"],
        ["pdm", "run", "pytest", "tests"],
        ["hatch", "run", "pytest", "tests"],
        ["rye", "run", "pytest", "tests"],
        ["coverage", "run", "-m", "pytest", "tests"],
        ["python", "-m", "coverage", "run", "-m", "pytest"],
        ["sudo", "uv", "run", "pytest", "tests"],
    ],
)
def test_should_recognize_pytest_invocation_forms(
    all_segment_tokens: list[str],
) -> None:
    assert segment_runs_pytest(all_segment_tokens) is True


@pytest.mark.parametrize(
    "all_segment_tokens",
    [
        ["git", "status"],
        ["python", "-m", "mypy", "."],
        ["python", "myscript.py", "-m", "pytest"],
        ["uv", "run", "--with", "pytest", "mypy", "."],
        ["uv", "sync"],
        ["uv", "tool", "install", "pytest"],
        ["coverage", "run", "-m", "mypy", "."],
        ["coverage", "report"],
        ["sudo", "apt", "update"],
        ["pyright", "-m", "pytest", "."],
        ["echo", "pytest"],
        ["ls", "pytest"],
        [],
    ],
)
def test_should_allow_non_pytest_segment_forms(
    all_segment_tokens: list[str],
) -> None:
    assert segment_runs_pytest(all_segment_tokens) is False


@pytest.mark.parametrize(
    "all_segment_tokens",
    [
        ["bash", "-c", "pytest tests"],
        ["bash", "-euc", "pytest tests"],
        ["bash", "-euo", "pipefail", "-c", "python -m pytest"],
        ["sh", "-c", "pytest tests"],
        ["pwsh", "-Command", "pytest tests"],
        ["cmd", "/c", "python", "-m", "pytest", "tests"],
    ],
)
def test_should_recognize_shell_string_exec_pytest(
    all_segment_tokens: list[str],
) -> None:
    assert segment_reports_a_pytest_exit_code(all_segment_tokens) is True


@pytest.mark.parametrize(
    "all_segment_tokens",
    [
        ["bash", "scripts/ci.sh", "-c", "pytest tests"],
        ["bash", "--", "-c", "pytest tests"],
        ["bash", "-Cu", "script.sh"],
        ["pwsh", "-NonInteractive", "-File", "a.ps1"],
        ["bash", "script.sh"],
    ],
)
def test_should_allow_shell_forms_that_do_not_run_pytest(
    all_segment_tokens: list[str],
) -> None:
    assert segment_reports_a_pytest_exit_code(all_segment_tokens) is False


def test_should_classify_segments_from_pipeline_parser() -> None:
    all_pairs = pipeline_segments_for_command("uv run pytest tests | tee out.log")
    assert len(all_pairs) >= 2
    assert segment_runs_pytest(all_pairs[0][0]) is True
    assert segment_runs_pytest(all_pairs[1][0]) is False


def test_should_not_false_classify_option_value_named_pytest() -> None:
    all_tokens = _first_segment_tokens("uv run --with pytest mypy .")
    assert segment_runs_pytest(all_tokens) is False


def test_should_not_false_classify_script_argument_named_pytest() -> None:
    all_tokens = _first_segment_tokens("python myscript.py -m pytest")
    assert segment_runs_pytest(all_tokens) is False
