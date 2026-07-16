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
HARNESS_USER_DIRECTORY_WINDOWS = "claude"
WINDOWS_MANGLED_WORKING_DIRECTORY = "c--Users-dev--claude-project"
SESSION_ID_ENVIRONMENT_VARIABLE = "CLAUDE_CODE_SESSION_ID"


def _load_shared_module() -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        "code_rules_shared_under_test", SHARED_MODULE_PATH
    )
    assert module_spec is not None and module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


_SHARED_MODULE = _load_shared_module()


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


def _build_windows_scratchpad_directory(temporary_root: Path) -> Path:
    """Build the Windows-shaped scratchpad directory that carries no user id segment."""
    scratchpad_directory = (
        temporary_root
        / HARNESS_USER_DIRECTORY_WINDOWS
        / WINDOWS_MANGLED_WORKING_DIRECTORY
        / SESSION_ID
        / "scratchpad"
    )
    scratchpad_directory.mkdir(parents=True)
    return scratchpad_directory


def _simulate_windows_platform(monkeypatch: pytest.MonkeyPatch, temporary_root: Path) -> None:
    monkeypatch.delattr(os, "getuid", raising=False)
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temporary_root))


def _session_payload() -> dict[str, str]:
    return {"cwd": WORKING_DIRECTORY, "session_id": SESSION_ID}


def test_returns_true_for_file_inside_reconstructed_scratchpad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    _point_temporary_directory_at(monkeypatch, tmp_path)
    _build_scratchpad_directory(tmp_path)
    project_module = tmp_path / "elsewhere" / "orders.py"

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(project_module), _session_payload()) is False
    )


def test_resolves_symlink_into_scratchpad_to_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    _point_temporary_directory_at(monkeypatch, tmp_path)
    monkeypatch.delenv(SESSION_ID_ENVIRONMENT_VARIABLE, raising=False)
    scratchpad_directory = _build_scratchpad_directory(tmp_path)
    throwaway_script = scratchpad_directory / "one_off_tool.py"
    payload_without_session = {"cwd": WORKING_DIRECTORY}

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(throwaway_script), payload_without_session)
        is False
    )


def test_exempt_without_working_directory_signal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The platform-safe predicate keys on the session id and the temp-directory path
    shape, so a payload carrying the session id alone still exempts a real scratchpad
    target even when it omits the working directory."""
    _point_temporary_directory_at(monkeypatch, tmp_path)
    scratchpad_directory = _build_scratchpad_directory(tmp_path)
    throwaway_script = scratchpad_directory / "one_off_tool.py"
    payload_without_cwd = {"session_id": SESSION_ID}

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(throwaway_script), payload_without_cwd)
        is True
    )


def test_exempt_on_windows_without_getuid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On Windows the os.getuid attribute is absent, and a real scratchpad target still
    resolves as exempt through its temp-directory path shape and session id."""
    _point_temporary_directory_at(monkeypatch, tmp_path)
    scratchpad_directory = _build_scratchpad_directory(tmp_path)
    throwaway_script = scratchpad_directory / "one_off_tool.py"
    monkeypatch.delattr(os, "getuid", raising=False)

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(throwaway_script), _session_payload())
        is True
    )


def test_nonexistent_scratchpad_directory_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    _point_temporary_directory_at(monkeypatch, tmp_path)
    _build_scratchpad_directory(tmp_path)

    assert _SHARED_MODULE.is_under_session_scratchpad("", _session_payload()) is False


def test_windows_shape_scratchpad_write_is_exempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A target under the Windows scratchpad shape (claude/<mangled>/<session>/scratchpad)
    resolves as exempt even though no user-id segment sits under the temp root."""
    _simulate_windows_platform(monkeypatch, tmp_path)
    scratchpad_directory = _build_windows_scratchpad_directory(tmp_path)
    throwaway_script = scratchpad_directory / "one_off_tool.py"

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(throwaway_script), _session_payload())
        is True
    )


def test_windows_shape_repository_file_is_not_exempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _simulate_windows_platform(monkeypatch, tmp_path)
    _build_windows_scratchpad_directory(tmp_path)
    repository_module = tmp_path / "repository" / "src" / "orders.py"
    repository_module.parent.mkdir(parents=True)

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(repository_module), _session_payload())
        is False
    )


def test_temp_path_outside_scratchpad_shape_is_not_exempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path under the harness user directory but off the session/scratchpad shape
    keeps full enforcement."""
    _simulate_windows_platform(monkeypatch, tmp_path)
    _build_windows_scratchpad_directory(tmp_path)
    off_shape_target = tmp_path / HARNESS_USER_DIRECTORY_WINDOWS / "unrelated" / "notes.py"
    off_shape_target.parent.mkdir(parents=True)

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(off_shape_target), _session_payload())
        is False
    )


def test_repository_path_containing_scratchpad_word_is_not_exempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repository path outside the temp directory that merely carries a scratchpad
    segment keeps full enforcement."""
    _simulate_windows_platform(monkeypatch, tmp_path)
    _build_windows_scratchpad_directory(tmp_path)
    repository_lookalike = tmp_path.parent / "project_repo" / "scratchpad" / "tool.py"

    assert (
        _SHARED_MODULE.is_under_session_scratchpad(str(repository_lookalike), _session_payload())
        is False
    )


def test_is_ephemeral_path_true_for_windows_scratchpad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _simulate_windows_platform(monkeypatch, tmp_path)
    scratchpad_directory = _build_windows_scratchpad_directory(tmp_path)
    throwaway_script = scratchpad_directory / "probe.py"

    assert _SHARED_MODULE.is_ephemeral_path(str(throwaway_script), _session_payload()) is True


def test_is_ephemeral_path_true_for_root_anchored_tmp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)

    assert _SHARED_MODULE.is_ephemeral_path("/tmp/scratch.py") is True


def test_is_ephemeral_path_false_for_repository_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _simulate_windows_platform(monkeypatch, tmp_path)
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    repository_file = tmp_path / "repository" / "orders.py"
    repository_file.parent.mkdir(parents=True)

    assert _SHARED_MODULE.is_ephemeral_path(str(repository_file), _session_payload()) is False


def test_is_ephemeral_path_reads_session_id_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no payload, the session scratchpad match reads the session id from the
    harness environment variable, so a caller that holds no payload still matches."""
    _simulate_windows_platform(monkeypatch, tmp_path)
    monkeypatch.setenv(SESSION_ID_ENVIRONMENT_VARIABLE, SESSION_ID)
    scratchpad_directory = _build_windows_scratchpad_directory(tmp_path)
    throwaway_script = scratchpad_directory / "probe.py"

    assert _SHARED_MODULE.is_ephemeral_path(str(throwaway_script)) is True
