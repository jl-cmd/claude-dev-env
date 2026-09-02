"""Tests for windows_safe_rmtree."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

from unittest.mock import patch

from windows_safe_rmtree import _strip_read_only_and_retry, main, remove_tree


def test_strip_read_only_and_retry_logs_when_retry_still_fails(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """The chmod-then-retry handler must surface residual failures to stderr."""
    target_path = tmp_path / "locked_file.txt"
    target_path.write_text("payload", encoding="utf-8")

    def always_fails(_path: str) -> None:
        raise PermissionError("file held by another process")

    _strip_read_only_and_retry(always_fails, str(target_path), None, None, None)
    captured = capsys.readouterr()
    assert str(target_path) in captured.err
    assert "PermissionError" in captured.err or "held by another process" in captured.err


def test_remove_tree_returns_nonzero_when_residual_oserror(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """When shutil.rmtree raises after handler retries, remove_tree must signal."""
    target_path = tmp_path / "ghost"
    target_path.mkdir()
    with patch(
        "shutil.rmtree",
        side_effect=PermissionError("residual lock"),
    ):
        exit_code = remove_tree(str(target_path))
    captured = capsys.readouterr()
    assert exit_code != 0, "remove_tree must report failure when rmtree raises"
    assert str(target_path) in captured.err
    assert "residual lock" in captured.err or "PermissionError" in captured.err


def test_main_propagates_remove_tree_failure(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """main must return non-zero when remove_tree could not finish cleanup."""
    target_path = tmp_path / "stubborn"
    target_path.mkdir()
    with patch(
        "shutil.rmtree",
        side_effect=PermissionError("still locked"),
    ):
        exit_code = main(["windows_safe_rmtree.py", str(target_path)])
    assert exit_code != 0


def test_remove_tree_deletes_plain_directory(tmp_path: Path) -> None:
    target = tmp_path / "victim"
    target.mkdir()
    (target / "file.txt").write_text("payload", encoding="utf-8")
    remove_tree(str(target))
    assert not target.exists()


def test_remove_tree_handles_read_only_file(tmp_path: Path) -> None:
    target = tmp_path / "victim"
    target.mkdir()
    locked_file = target / "locked.txt"
    locked_file.write_text("payload", encoding="utf-8")
    os.chmod(locked_file, stat.S_IREAD)
    remove_tree(str(target))
    assert not target.exists()


def test_remove_tree_swallows_missing_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "does-not-exist"
    remove_tree(str(missing_path))


def test_main_returns_zero_on_success(tmp_path: Path) -> None:
    target = tmp_path / "victim"
    target.mkdir()
    exit_code = main(["windows_safe_rmtree.py", str(target)])
    assert exit_code == 0
    assert not target.exists()


def test_main_returns_usage_exit_code_when_argv_count_wrong(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["windows_safe_rmtree.py"])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "usage" in captured.err.lower()
