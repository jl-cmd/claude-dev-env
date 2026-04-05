"""Tests for mypy integration module."""

from pathlib import Path
from unittest.mock import patch

from mypy_integration import MypyResult, check_mypy_available, run_mypy_check


def test_mypy_result_dataclass() -> None:
    """Test MypyResult dataclass creation."""
    result = MypyResult(passed=True, output="test", error_count=0)
    assert result.passed is True
    assert result.output == "test"
    assert result.error_count == 0


def test_check_mypy_available_returns_false_when_not_installed() -> None:
    """Test that check_mypy_available returns False when mypy not found."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert check_mypy_available() is False


def test_run_mypy_check_returns_passed_for_empty_files() -> None:
    """Test that run_mypy_check passes with no files."""
    result = run_mypy_check([])
    assert result.passed is True
    assert "No files" in result.output
