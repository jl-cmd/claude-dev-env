"""Tests for sweep_empty_dirs script behaviors."""

import argparse
import errno
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS_DIR = Path(os.path.abspath(__file__)).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sweep_empty_dirs import _build_parser, _positive_int, sweep  # noqa: E402

_OLD_TIMESTAMP = time.time() - 300


def test_positive_int_accepts_valid_value() -> None:
    """_positive_int accepts integers >= 1."""
    assert _positive_int("5") == 5


def test_positive_int_accepts_minimum_value() -> None:
    """_positive_int accepts exactly 1."""
    assert _positive_int("1") == 1


def test_positive_int_rejects_zero() -> None:
    """_positive_int raises for 0."""
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_int("0")


def test_positive_int_rejects_negative() -> None:
    """_positive_int raises for negative values."""
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_int("-1")


def test_positive_int_rejects_non_integer() -> None:
    """_positive_int raises for non-integer strings like 'abc'."""
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_int("abc")


def test_build_parser_sets_age_default_from_timing_config() -> None:
    """_build_parser uses DEFAULT_AGE_SECONDS from dev_env_scripts_constants.timing as --age default."""
    parser = _build_parser()
    default_age = parser.get_default("age")
    assert isinstance(default_age, int)
    assert default_age > 0


def test_build_parser_sets_interval_default_from_timing_config() -> None:
    """_build_parser uses DEFAULT_POLL_INTERVAL from dev_env_scripts_constants.timing as --interval default."""
    parser = _build_parser()
    default_interval = parser.get_default("interval")
    assert isinstance(default_interval, int)
    assert default_interval > 0


def test_sweep_removes_empty_directory(tmp_path: Path) -> None:
    """sweep removes an empty directory older than the age threshold."""
    empty_dir = tmp_path / "empty_old"
    empty_dir.mkdir()

    sweep(str(tmp_path), min_age_seconds=0)

    assert not empty_dir.exists()


def test_sweep_preserves_non_empty_directory(tmp_path: Path) -> None:
    """sweep does not remove a directory containing files."""
    non_empty_dir = tmp_path / "has_files"
    non_empty_dir.mkdir()
    (non_empty_dir / "some_file.txt").write_text("content")

    sweep(str(tmp_path), min_age_seconds=0)

    assert non_empty_dir.exists()


def test_sweep_preserves_root_directory(tmp_path: Path) -> None:
    """sweep never removes the root directory itself."""
    sub_dir = tmp_path / "subdir"
    sub_dir.mkdir()

    sweep(str(tmp_path), min_age_seconds=0)

    assert tmp_path.exists()


def test_sweep_removes_nested_empty_dirs(tmp_path: Path) -> None:
    """sweep removes nested empty directories bottom-up."""
    nested = tmp_path / "level1" / "level2" / "level3"
    nested.mkdir(parents=True)

    sweep(str(tmp_path), min_age_seconds=0)

    assert not nested.exists()
    assert not (tmp_path / "level1" / "level2").exists()
    assert not (tmp_path / "level1").exists()


def test_sweep_removes_only_old_enough_directories(tmp_path: Path) -> None:
    """sweep does not remove directories newer than the age threshold."""
    young_dir = tmp_path / "young"
    young_dir.mkdir()

    sweep(str(tmp_path), min_age_seconds=9999999)

    assert young_dir.exists()


def test_sweep_returns_list_of_removed_directories(tmp_path: Path) -> None:
    """sweep returns the paths of directories it removed."""
    old_dir = tmp_path / "old_empty"
    old_dir.mkdir()

    removed = sweep(str(tmp_path), min_age_seconds=0)

    assert old_dir.name in [Path(p).name for p in removed]


def test_skips_dir_when_getctime_raises_os_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        problem_dir = os.path.join(tmp, "broken")
        os.mkdir(problem_dir)

        original_getctime = os.path.getctime

        def _failing_getctime(path: str) -> float:
            if "broken" in path:
                raise OSError("simulated broken junction")
            return original_getctime(path)

        with patch("os.path.getctime", side_effect=_failing_getctime):
            removed = sweep(tmp, min_age_seconds=120)

        assert problem_dir not in removed
        assert os.path.isdir(problem_dir)


def test_suppresses_eexist_like_enotempty() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        non_empty_dir = os.path.join(tmp, "occupied")
        os.mkdir(non_empty_dir)
        _touch(os.path.join(non_empty_dir, "a_file"))

        target_dir = os.path.join(tmp, "empty_target")
        os.mkdir(target_dir)

        def _mock_getctime(directory_path: str) -> float:
            return _OLD_TIMESTAMP

        original_rmdir = os.rmdir

        def _rmdir_raise_eexist(removal_path: str) -> None:
            if "occupied" in removal_path:
                raise OSError(errno.EEXIST, "Directory not empty")
            original_rmdir(removal_path)

        with (
            patch("os.path.getctime", side_effect=_mock_getctime),
            patch("os.rmdir", side_effect=_rmdir_raise_eexist),
        ):
            removed = sweep(tmp, min_age_seconds=120)

        assert target_dir in removed
        assert os.path.isdir(non_empty_dir)


def _touch(file_path: str) -> None:
    Path(file_path).write_text("")
