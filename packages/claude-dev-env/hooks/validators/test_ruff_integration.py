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
