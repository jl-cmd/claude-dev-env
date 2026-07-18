"""Tests for the ruff integration module."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from .ruff_integration import (
    RuffResult,
    _config_relative_stdin_filename,
    _parse_fixed_count,
    check_ruff_available,
    find_pyproject_with_ruff_config,
    run_ruff_check,
)


def test_parse_fixed_count_reads_the_count_from_the_fixed_line() -> None:
    """The ``Fixed N`` summary line yields its integer count."""
    assert _parse_fixed_count("Found 3 errors (2 fixed).\nFixed 2 errors\n") == 2


def test_parse_fixed_count_returns_zero_without_a_fixed_line() -> None:
    """Output with no ``Fixed`` line yields a zero count."""
    assert _parse_fixed_count("All checks passed!\n") == 0


def test_parse_fixed_count_scans_past_a_violation_line_quoting_fixed() -> None:
    """A violation line quoting ``Fixed`` does not stop the scan for the summary.

    ::

        x.py:3:1: F821 Undefined name `FixedWidth`   <- contains "Fixed", unparseable
        Fixed 2 errors.                               <- the real summary line

    A parse failure on the first ``Fixed``-containing line keeps scanning so the
    genuine ``Fixed N`` summary further down is still read.
    """
    violation_then_summary = (
        "x.py:3:1: F821 Undefined name `FixedWidth`\nFixed 2 errors."
    )

    assert _parse_fixed_count(violation_then_summary) == 2


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

    ::

        config source .../ruff_repo/asserts.py -> resolves .../ruff_repo/pyproject.toml
        ok: [tool.ruff.lint] select B applies to the staged copy -> B011 fires

    The assertions read the resolution mechanism directly — the config resolves
    from the original target and not from the detached staged tree — so the
    check does not depend on native discovery finding no config in the
    temp-directory ancestry, which a stray ancestor pyproject could perturb.
    """
    ruff_repo = tmp_path / "ruff_repo"
    ruff_repo.mkdir()
    ruff_pyproject = ruff_repo / "pyproject.toml"
    ruff_pyproject.write_text("[tool.ruff.lint]\nselect = ['B']\n", encoding="utf-8")
    original_target = ruff_repo / "asserts.py"
    staged_copy = tmp_path / "detached" / "asserts.py"
    staged_copy.parent.mkdir(parents=True)
    staged_copy.write_text("def probe() -> None:\n    assert False\n", encoding="utf-8")

    with_source = run_ruff_check([staged_copy], config_source_path=original_target)

    assert find_pyproject_with_ruff_config(original_target) == ruff_pyproject
    assert find_pyproject_with_ruff_config(staged_copy) != ruff_pyproject
    assert "B011" in with_source.output


def test_run_ruff_check_falls_back_to_native_config_when_staged_copy_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable staged copy still grades under the resolved project config.

    ::

        _read_staged_content -> None (unreadable), config selects B
        ok: native fallback lints the temp path under resolved --config -> B011

    The native last-resort path applies the resolved project config but lints
    the temp path directly, so path-scoped per-file-ignores keyed to the
    original relative name do not apply. ``_read_staged_content`` is patched to
    return None, the signal an OSError raises in production.
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
    ruff_module = sys.modules[run_ruff_check.__module__]
    monkeypatch.setattr(ruff_module, "_read_staged_content", lambda _staged: None)

    fallback_result = run_ruff_check([staged_copy], config_source_path=original_target)

    assert "B011" in fallback_result.output


def test_run_ruff_check_honors_extend_exclude_over_stdin(tmp_path: Path) -> None:
    """A target the config's extend-exclude opts out of linting stays unflagged.

    ::

        config extend-exclude = ["excluded_probe.py"], target under it, F401 source
        ok: --force-exclude makes ruff skip the excluded target over stdin -> passes

    Ruff applies exclude rules to stdin content only when ``--force-exclude`` is
    on the argv, so the staged command must carry it for extend-exclude fidelity.
    """
    ruff_repo = tmp_path / "ruff_repo"
    ruff_repo.mkdir()
    (ruff_repo / "pyproject.toml").write_text(
        "[tool.ruff]\nextend-exclude = ['excluded_probe.py']\n", encoding="utf-8"
    )
    original_target = ruff_repo / "excluded_probe.py"
    staged_copy = tmp_path / "detached" / "excluded_probe.py"
    staged_copy.parent.mkdir(parents=True)
    staged_copy.write_text("import os\n", encoding="utf-8")

    excluded_result = run_ruff_check([staged_copy], config_source_path=original_target)

    assert "F401" not in excluded_result.output
    assert excluded_result.passed


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
