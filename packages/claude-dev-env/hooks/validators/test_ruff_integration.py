"""Tests for ruff integration module."""

from pathlib import Path
from unittest.mock import patch

from .ruff_integration import RuffResult, check_ruff_available, run_ruff_check


def test_ruff_result_dataclass() -> None:
    """Test RuffResult dataclass creation."""
    result = RuffResult(passed=True, output="test", fixed_count=0)
    assert result.passed is True
    assert result.output == "test"
    assert result.fixed_count == 0


def test_check_ruff_available_returns_false_when_not_installed() -> None:
    """Test that check_ruff_available returns False when ruff not found."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert check_ruff_available() is False


def test_run_ruff_check_returns_passed_for_empty_files() -> None:
    """Test that run_ruff_check passes with no files."""
    result = run_ruff_check([])
    assert result.passed is True
    assert "No files" in result.output


def test_run_ruff_check_emits_location_prefixed_lines(tmp_path: Path) -> None:
    """Each reported violation carries a ``path:line:col:`` prefix on its own line.

    The run_all_validators PreToolUse gate parses these prefixes to scope
    violations to a baseline, so the output format is pinned to the concise
    shape rather than the ruff default, which moved locations onto separate
    ``-->`` lines.
    """
    violating_file = tmp_path / "unused_import_module.py"
    violating_file.write_text("import os\n", encoding="utf-8")

    result = run_ruff_check([violating_file])

    assert result.passed is False
    location_prefix = f"{violating_file}:1:8:"
    assert any(
        each_line.startswith(location_prefix) and "F401" in each_line
        for each_line in result.output.splitlines()
    ), result.output
    assert "\x1b[" not in result.output
