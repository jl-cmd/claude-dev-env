"""Tests for ruff integration module."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from .ruff_integration import (
    RuffResult,
    _config_relative_stdin_filename,
    _parse_fixed_count,
    _staged_ruff_result,
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


def test_run_ruff_check_grades_a_staged_copy_holding_non_ascii_text(
    tmp_path: Path,
) -> None:
    """A staged copy carrying non-ASCII text reaches ruff intact.

    The staged shape pipes the copy's text to ruff on stdin, and ruff reads
    stdin as UTF-8. Encoding that pipe with the host locale codec instead
    hands ruff a byte it rejects, so every Python file holding a non-ASCII
    character fails the gate on a host whose locale codec is not UTF-8.
    """
    ruff_repo = tmp_path / "ruff_repo"
    ruff_repo.mkdir()
    (ruff_repo / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
    original_target = ruff_repo / "dashes.py"
    staged_copy = tmp_path / "detached" / "dashes.py"
    staged_copy.parent.mkdir(parents=True)
    staged_copy.write_text('DASH_NOTE = "an em dash — here"\n', encoding="utf-8")

    result = run_ruff_check([staged_copy], config_source_path=original_target)

    assert result.passed is True


def test_staged_ruff_result_pins_utf8_encoding_with_tolerant_decode(
    tmp_path: Path,
) -> None:
    """The staged ruff call pins UTF-8 and decodes ruff output tolerantly.

    ::

        subprocess.run(..., encoding="utf-8", errors="replace", ...)
        ok:   locale-independent stdin; a non-UTF-8 byte in ruff output never raises
        flag: encoding omitted -> locale codec; errors omitted -> strict decode
              raises out of subprocess.run on POSIX (fail-open in the gate)

    The kwargs carry the contract host-independently. The locale fallback the
    integration test above depends on cannot be forced portably, so this guard
    asserts the call itself rather than the emergent behavior.
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.ruff]\n", encoding="utf-8")
    captured_keyword_arguments: dict[str, object] = {}

    def record_call(*positional: object, **keyword: object) -> subprocess.CompletedProcess[str]:
        captured_keyword_arguments.update(keyword)
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=record_call):
        _staged_ruff_result(pyproject, "probe.py", "x = 1\n")

    assert captured_keyword_arguments["encoding"] == "utf-8"
    assert captured_keyword_arguments["errors"] == "replace"


def test_staged_ruff_result_tolerates_non_utf8_bytes_in_ruff_output(
    tmp_path: Path,
) -> None:
    """A non-UTF-8 byte in ruff's output is decoded tolerantly, not dropped.

    ::

        ruff output carries byte 0x92 (a cp1252 curly quote, invalid UTF-8)
        ok:   errors="replace" -> output keeps the surrounding text
        flag: errors="strict"  -> POSIX raises out of run; Windows drops the
              stream to None and the surrounding text is lost

    Swaps the ruff argv for a python one-liner emitting the bad byte, so the
    real subprocess decode path runs against real bytes.
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.ruff]\n", encoding="utf-8")
    emit_bad_byte_command = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.buffer.write(bytes([0x62, 0x92, 0x63]))",
    ]
    staged_module = sys.modules[_staged_ruff_result.__module__]
    with patch.object(
        staged_module, "_staged_ruff_command", return_value=emit_bad_byte_command
    ):
        result = _staged_ruff_result(pyproject, "probe.py", "x = 1\n")

    assert "b" in result.output
    assert "c" in result.output


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
