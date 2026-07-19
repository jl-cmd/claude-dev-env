"""Tests for orchestrator status_gate (status file + should-reschedule)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from status_gate_constants.config.constants import (  # noqa: E402
    ALL_DEFAULT_STATUS_DIRECTORY_PARTS,
    EXIT_CODE_STOP,
    EXIT_CODE_SUCCESS,
    REASON_ACTIVE,
    REASON_MISSING_STATUS_FILE,
    REASON_STATUS_NOT_ACTIVE,
    RUN_STATUS_ACTIVE,
    RUN_STATUS_DONE,
    STATUS_FIELD_NAME,
    STATUS_FILE_ENV_VAR,
    STATUS_FILE_NAME,
)


def load_status_gate_module() -> ModuleType:
    module_path = SCRIPTS_DIRECTORY / "status_gate.py"
    spec = importlib.util.spec_from_file_location("status_gate", module_path)
    assert spec is not None
    assert spec.loader is not None
    status_gate_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = status_gate_module
    spec.loader.exec_module(status_gate_module)
    return status_gate_module


class TestWriteAndDecide:
    def should_allow_reschedule_when_status_is_active(
        self, temporary_directory: Path
    ) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "run-status.json"
        status_gate.write_status_file(status_file_path, RUN_STATUS_ACTIVE, "")
        is_allowed, reason_code = status_gate.decide_should_reschedule(status_file_path)
        assert is_allowed is True
        assert reason_code == REASON_ACTIVE

    def should_stop_when_status_is_done(self, temporary_directory: Path) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "run-status.json"
        status_gate.write_status_file(status_file_path, RUN_STATUS_DONE, "")
        is_allowed, reason_code = status_gate.decide_should_reschedule(status_file_path)
        assert is_allowed is False
        assert reason_code == REASON_STATUS_NOT_ACTIVE

    def should_fail_closed_when_status_file_missing(
        self, temporary_directory: Path
    ) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "missing.json"
        is_allowed, reason_code = status_gate.decide_should_reschedule(status_file_path)
        assert is_allowed is False
        assert reason_code == REASON_MISSING_STATUS_FILE

    def should_fail_closed_when_status_file_is_invalid_json(
        self, temporary_directory: Path
    ) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "bad.json"
        status_file_path.write_text("{not-json", encoding="utf-8")
        is_allowed, reason_code = status_gate.decide_should_reschedule(status_file_path)
        assert is_allowed is False


class TestResolveAndCli:
    def should_resolve_explicit_status_file_path(
        self, temporary_directory: Path
    ) -> None:
        status_gate = load_status_gate_module()
        target_path = temporary_directory / "explicit.json"
        resolved_path = status_gate.resolve_status_file_path(
            str(target_path), None, ""
        )
        assert resolved_path == target_path.resolve()

    def should_resolve_default_path_under_base_directory(
        self, temporary_directory: Path
    ) -> None:
        status_gate = load_status_gate_module()
        resolved_path = status_gate.resolve_status_file_path(
            None, temporary_directory, ""
        )
        expected_path = temporary_directory.joinpath(
            *ALL_DEFAULT_STATUS_DIRECTORY_PARTS, STATUS_FILE_NAME
        ).resolve()
        assert resolved_path == expected_path

    def should_scope_default_path_by_run_slug(
        self, temporary_directory: Path
    ) -> None:
        status_gate = load_status_gate_module()
        run_slug = "demo-run"
        resolved_path = status_gate.resolve_status_file_path(
            None, temporary_directory, run_slug
        )
        expected_path = temporary_directory.joinpath(
            *ALL_DEFAULT_STATUS_DIRECTORY_PARTS, run_slug, STATUS_FILE_NAME
        ).resolve()
        assert resolved_path == expected_path

    def should_set_and_gate_via_main(
        self,
        temporary_directory: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "status.json"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "status_gate.py",
                "set",
                "--status-file",
                str(status_file_path),
                "--status",
                RUN_STATUS_ACTIVE,
                "--run-slug",
                "demo-run",
            ],
        )
        assert status_gate.main() == EXIT_CODE_SUCCESS
        payload = json.loads(status_file_path.read_text(encoding="utf-8"))
        assert payload[STATUS_FIELD_NAME] == RUN_STATUS_ACTIVE

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "status_gate.py",
                "should-reschedule",
                "--status-file",
                str(status_file_path),
            ],
        )
        assert status_gate.main() == EXIT_CODE_SUCCESS

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "status_gate.py",
                "set",
                "--status-file",
                str(status_file_path),
                "--status",
                RUN_STATUS_DONE,
            ],
        )
        assert status_gate.main() == EXIT_CODE_SUCCESS
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "status_gate.py",
                "should-reschedule",
                "--status-file",
                str(status_file_path),
            ],
        )
        assert status_gate.main() == EXIT_CODE_STOP

    def should_resolve_status_file_from_environment(
        self, temporary_directory: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "env-status.json"
        monkeypatch.setenv(STATUS_FILE_ENV_VAR, str(status_file_path))
        monkeypatch.setattr(
            sys,
            "argv",
            ["status_gate.py", "set", "--status", RUN_STATUS_ACTIVE],
        )
        assert status_gate.main() == EXIT_CODE_SUCCESS
        assert status_file_path.is_file()
        is_allowed, _reason = status_gate.decide_should_reschedule(status_file_path)
        assert is_allowed is True

    def should_scope_set_and_should_reschedule_with_matching_run_slug(
        self, temporary_directory: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status_gate = load_status_gate_module()
        monkeypatch.chdir(temporary_directory)
        monkeypatch.delenv(STATUS_FILE_ENV_VAR, raising=False)
        run_slug = "demo-run"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "status_gate.py",
                "set",
                "--status",
                RUN_STATUS_ACTIVE,
                "--run-slug",
                run_slug,
            ],
        )
        assert status_gate.main() == EXIT_CODE_SUCCESS
        slug_path = status_gate.resolve_status_file_path(
            None, temporary_directory, run_slug
        )
        default_path = status_gate.resolve_status_file_path(
            None, temporary_directory, ""
        )
        assert slug_path.is_file()
        assert not default_path.is_file()
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "status_gate.py",
                "should-reschedule",
                "--run-slug",
                run_slug,
            ],
        )
        assert status_gate.main() == EXIT_CODE_SUCCESS
        monkeypatch.setattr(
            sys,
            "argv",
            ["status_gate.py", "should-reschedule"],
        )
        assert status_gate.main() == EXIT_CODE_STOP


@pytest.fixture
def temporary_directory(tmp_path: Path) -> Path:
    return tmp_path
