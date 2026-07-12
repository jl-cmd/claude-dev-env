"""Tests for the harness session scratchpad exemption in code_rules_shared."""

import importlib.util
import os
import tempfile
from pathlib import Path
from types import ModuleType

import pytest

SHARED_MODULE_PATH = Path(__file__).parent / "code_rules_shared.py"
FIXED_USER_ID = 4242
WORKING_DIRECTORY = "/home/user/project"
SESSION_ID = "session-abc-123"


def _load_shared_module() -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        "code_rules_shared_under_test", SHARED_MODULE_PATH
    )
    assert module_spec is not None and module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


_SHARED_MODULE = _load_shared_module()


def _install_fixed_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "getuid", lambda: FIXED_USER_ID, raising=False)


def _point_temporary_directory_at(monkeypatch: pytest.MonkeyPatch, temporary_root: Path) -> None:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temporary_root))


def _build_scratchpad_directory(temporary_root: Path) -> Path:
    mangled_working_directory = WORKING_DIRECTORY.replace("/", "-")
    scratchpad_directory = (
        temporary_root
        / f"claude-{FIXED_USER_ID}"
        / mangled_working_directory
        / SESSION_ID
        / "scratchpad"
    )
    scratchpad_directory.mkdir(parents=True)
    return scratchpad_directory


def _session_payload() -> dict[str, str]:
    return {"cwd": WORKING_DIRECTORY, "session_id": SESSION_ID}


def test_returns_true_for_file_inside_reconstructed_scratchpad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fixed_user_id(monkeypatch)
    _point_temporary_directory_at(monkeypatch, tmp_path)
    scratchpad_directory = _build_scratchpad_directory(tmp_path)
    throwaway_script = scratchpad_directory / "one_off_tool.py"

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(throwaway_script), _session_payload())
        is True
    )


def test_returns_false_for_file_outside_scratchpad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fixed_user_id(monkeypatch)
    _point_temporary_directory_at(monkeypatch, tmp_path)
    _build_scratchpad_directory(tmp_path)
    project_module = tmp_path / "elsewhere" / "orders.py"

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(project_module), _session_payload()) is False
    )


def test_resolves_symlink_into_scratchpad_to_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fixed_user_id(monkeypatch)
    _point_temporary_directory_at(monkeypatch, tmp_path)
    scratchpad_directory = _build_scratchpad_directory(tmp_path)
    real_script = scratchpad_directory / "real_tool.py"
    real_script.write_text("value = 1\n")
    link_outside = tmp_path / "link_to_scratchpad.py"
    link_outside.symlink_to(real_script)

    assert _SHARED_MODULE.is_under_session_scratchpad(str(link_outside), _session_payload()) is True


def test_symlink_resolving_outside_scratchpad_is_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fixed_user_id(monkeypatch)
    _point_temporary_directory_at(monkeypatch, tmp_path)
    scratchpad_directory = _build_scratchpad_directory(tmp_path)
    real_target_outside = tmp_path / "outside_target.py"
    real_target_outside.write_text("value = 1\n")
    link_inside_scratchpad = scratchpad_directory / "sneaky_link.py"
    link_inside_scratchpad.symlink_to(real_target_outside)

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(link_inside_scratchpad), _session_payload())
        is False
    )


def test_missing_session_id_signal_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fixed_user_id(monkeypatch)
    _point_temporary_directory_at(monkeypatch, tmp_path)
    scratchpad_directory = _build_scratchpad_directory(tmp_path)
    throwaway_script = scratchpad_directory / "one_off_tool.py"
    payload_without_session = {"cwd": WORKING_DIRECTORY}

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(throwaway_script), payload_without_session)
        is False
    )


def test_missing_working_directory_signal_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fixed_user_id(monkeypatch)
    _point_temporary_directory_at(monkeypatch, tmp_path)
    scratchpad_directory = _build_scratchpad_directory(tmp_path)
    throwaway_script = scratchpad_directory / "one_off_tool.py"
    payload_without_cwd = {"session_id": SESSION_ID}

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(throwaway_script), payload_without_cwd)
        is False
    )


def test_absent_getuid_returns_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fixed_user_id(monkeypatch)
    _point_temporary_directory_at(monkeypatch, tmp_path)
    scratchpad_directory = _build_scratchpad_directory(tmp_path)
    throwaway_script = scratchpad_directory / "one_off_tool.py"
    monkeypatch.delattr(os, "getuid", raising=False)

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(throwaway_script), _session_payload())
        is False
    )


def test_nonexistent_scratchpad_directory_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fixed_user_id(monkeypatch)
    _point_temporary_directory_at(monkeypatch, tmp_path)
    mangled_working_directory = WORKING_DIRECTORY.replace("/", "-")
    unbuilt_target = (
        tmp_path
        / f"claude-{FIXED_USER_ID}"
        / mangled_working_directory
        / SESSION_ID
        / "scratchpad"
        / "one_off_tool.py"
    )

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(unbuilt_target), _session_payload()) is False
    )


def test_empty_file_path_returns_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fixed_user_id(monkeypatch)
    _point_temporary_directory_at(monkeypatch, tmp_path)
    _build_scratchpad_directory(tmp_path)

    assert _SHARED_MODULE.is_under_session_scratchpad("", _session_payload()) is False
