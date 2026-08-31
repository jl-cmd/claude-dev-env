"""Tests for the shared system-temp root membership helper."""

from pathlib import Path

import pytest

from .system_temporary_roots import (
    all_system_temporary_roots,
    enclosing_system_temporary_root,
)


def test_all_system_temporary_roots_includes_runner_temp_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RUNNER_TEMP joins gettempdir so GHA basetemp counts as system temp."""
    runner_temp_root = tmp_path / "runner_temp"
    os_gettemp = tmp_path / "os_gettemp"
    runner_temp_root.mkdir()
    os_gettemp.mkdir()
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp_root))
    monkeypatch.setattr(
        "validators.system_temporary_roots.tempfile.gettempdir",
        lambda: str(os_gettemp),
    )

    all_roots = all_system_temporary_roots()

    assert os_gettemp.resolve() in all_roots
    assert runner_temp_root.resolve() in all_roots


def test_enclosing_system_temporary_root_returns_gettempdir_for_file_under_it(
    tmp_path: Path,
) -> None:
    """A pytest tmp_path file sits under the process temp root."""
    nested_file = tmp_path / "detached" / "module.py"
    nested_file.parent.mkdir()
    nested_file.write_text("sample_number: int = 1\n", encoding="utf-8")

    enclosing_root = enclosing_system_temporary_root(nested_file)

    assert enclosing_root is not None
    assert nested_file.resolve().is_relative_to(enclosing_root)


def test_enclosing_system_temporary_root_uses_runner_temp_when_gettempdir_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GHA basetemp lives under RUNNER_TEMP while gettempdir is often another root.

    ::

        RUNNER_TEMP/detached/module.py, gettempdir -> sibling os_gettemp
        ok:   enclosing root is RUNNER_TEMP
        flag: gettempdir-only helper returns None and the mypy walk climbs out
    """
    runner_temp_root = tmp_path / "runner_temp"
    os_gettemp = tmp_path / "os_gettemp"
    runner_temp_root.mkdir()
    os_gettemp.mkdir()
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp_root))
    monkeypatch.setattr(
        "validators.system_temporary_roots.tempfile.gettempdir",
        lambda: str(os_gettemp),
    )
    nested_file = runner_temp_root / "detached" / "module.py"
    nested_file.parent.mkdir()
    nested_file.write_text("sample_number: int = 1\n", encoding="utf-8")

    assert enclosing_system_temporary_root(nested_file) == runner_temp_root.resolve()


def test_enclosing_system_temporary_root_returns_none_outside_every_temp_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path outside gettempdir and the temp env vars is not a staging copy."""
    os_gettemp = tmp_path / "os_gettemp"
    project_root = tmp_path / "project"
    os_gettemp.mkdir()
    project_root.mkdir()
    monkeypatch.delenv("RUNNER_TEMP", raising=False)
    monkeypatch.delenv("TEMP", raising=False)
    monkeypatch.delenv("TMP", raising=False)
    monkeypatch.delenv("TMPDIR", raising=False)
    monkeypatch.setattr(
        "validators.system_temporary_roots.tempfile.gettempdir",
        lambda: str(os_gettemp),
    )
    project_file = project_root / "module.py"
    project_file.write_text("sample_number: int = 1\n", encoding="utf-8")

    assert enclosing_system_temporary_root(project_file) is None
