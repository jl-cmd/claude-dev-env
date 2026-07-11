"""Tests for mypy integration module."""

from pathlib import Path
from unittest.mock import patch

from .mypy_integration import (
    MypyResult,
    check_mypy_available,
    find_pyproject_with_mypy_config,
    run_mypy_check,
)


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


def test_find_pyproject_returns_pyproject_with_tool_mypy(tmp_path: Path) -> None:
    project_root = tmp_path / "myproj"
    nested_dir = project_root / "src" / "deep"
    nested_dir.mkdir(parents=True)
    project_pyproject = project_root / "pyproject.toml"
    project_pyproject.write_text("[tool.mypy]\nignore_missing_imports = true\n")
    target_file = nested_dir / "module.py"
    target_file.write_text("x: int = 1\n")
    found_path = find_pyproject_with_mypy_config(target_file)
    assert found_path == project_pyproject


def test_find_pyproject_skips_pyproject_without_tool_mypy(tmp_path: Path) -> None:
    outer_root = tmp_path / "outer"
    inner_root = outer_root / "inner"
    inner_root.mkdir(parents=True)
    outer_pyproject = outer_root / "pyproject.toml"
    outer_pyproject.write_text("[tool.mypy]\nignore_missing_imports = true\n")
    inner_pyproject = inner_root / "pyproject.toml"
    inner_pyproject.write_text("[project]\nname = 'inner-package'\n")
    target_file = inner_root / "module.py"
    target_file.write_text("y: str = 'hello'\n")
    found_path = find_pyproject_with_mypy_config(target_file)
    assert found_path == outer_pyproject


def test_find_pyproject_returns_none_when_no_match(tmp_path: Path) -> None:
    isolated_dir = tmp_path / "isolated"
    isolated_dir.mkdir()
    target_file = isolated_dir / "module.py"
    target_file.write_text("z: float = 1.0\n")
    assert find_pyproject_with_mypy_config(target_file) is None


def test_find_pyproject_handles_malformed_toml(tmp_path: Path) -> None:
    project_root = tmp_path / "broken"
    project_root.mkdir()
    project_pyproject = project_root / "pyproject.toml"
    project_pyproject.write_text("[tool.mypy\nbroken = true\n")
    target_file = project_root / "module.py"
    target_file.write_text("a = 1\n")
    assert find_pyproject_with_mypy_config(target_file) is None
