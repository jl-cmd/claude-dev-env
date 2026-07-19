"""Tests for ruff integration module."""

from pathlib import Path
from unittest.mock import patch

from .ruff_integration import (
    RuffResult,
    _config_relative_stdin_filename,
    _parse_fixed_count,
    check_ruff_available,
    run_ruff_check,
)


def test_parse_fixed_count_reads_the_count_from_the_fixed_line() -> None:
    """The ``Fixed N`` summary line yields its integer count."""
    assert _parse_fixed_count("Found 3 errors (2 fixed).\nFixed 2 errors\n") == 2


def test_parse_fixed_count_returns_zero_without_a_fixed_line() -> None:
    """Output with no ``Fixed`` line yields a zero count."""
    assert _parse_fixed_count("All checks passed!\n") == 0


def test_config_relative_stdin_filename_returns_posix_path_under_config_directory() -> None:
    """A target under the config directory resolves to its config-relative path."""
    config_directory = Path("/repo/hooks")
    target_path = Path("/repo/hooks/validators/run_all_validators.py")

    relative_filename = _config_relative_stdin_filename(target_path, config_directory)

    assert relative_filename == "validators/run_all_validators.py"


def test_config_relative_stdin_filename_falls_back_to_basename_off_tree() -> None:
    """A target outside the config directory falls back to the bare basename.

    Path-scoped per-file-ignores cannot apply to a file that does not sit under
    the config directory, so a ``..``-laden relative path is never handed to ruff.
    """
    config_directory = Path("/repo/hooks")
    target_path = Path("/elsewhere/run_all_validators.py")

    relative_filename = _config_relative_stdin_filename(target_path, config_directory)

    assert relative_filename == "run_all_validators.py"


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
    assert result.fixed_count == 0
    assert "No files" in result.output


def test_run_ruff_check_applies_config_resolved_from_config_source_path(
    tmp_path: Path,
) -> None:
    """A given config_source_path resolves the ruff config for a staged copy.

    A ``[tool.ruff.lint]`` selecting B flags an ``assert False`` (B011) only when
    ``config_source_path`` — the original ``.py`` target — resolves it; native
    discovery from the detached staged copy finds no ruff config and passes.
    """
    ruff_repo = tmp_path / "ruff_repo"
    ruff_repo.mkdir()
    (ruff_repo / "pyproject.toml").write_text(
        "[tool.ruff.lint]\nselect = ['B']\n", encoding="utf-8"
    )
    original_target = ruff_repo / "asserts.py"
    staged_copy = tmp_path / "detached" / "asserts.py"
    staged_copy.parent.mkdir(parents=True)
    staged_copy.write_text("def probe() -> None:\n    assert False\n", encoding="utf-8")

    without_source = run_ruff_check([staged_copy])
    with_source = run_ruff_check([staged_copy], config_source_path=original_target)

    assert "B011" not in without_source.output
    assert "B011" in with_source.output


def test_run_ruff_check_emits_location_prefixed_lines(tmp_path: Path) -> None:
    """Each reported violation carries a ``path:line:col:`` prefix on its own line.

    The run_all_validators PreToolUse gate parses these prefixes to scope
    violations to a baseline, so the output format is pinned to the concise
    shape rather than the ruff default, which moved locations onto separate
    ``-->`` lines.
    """
    violating_file = tmp_path / "unused_import_module.py"
    violating_file.write_text("import os\n", encoding="utf-8")

    with patch.dict("os.environ", {"FORCE_COLOR": "1"}):
        result = run_ruff_check([violating_file])

    assert result.passed is False
    location_prefix = f"{violating_file}:1:8:"
    assert any(
        each_line.startswith(location_prefix) and "F401" in each_line
        for each_line in result.output.splitlines()
    ), result.output
    assert "\x1b[" not in result.output
