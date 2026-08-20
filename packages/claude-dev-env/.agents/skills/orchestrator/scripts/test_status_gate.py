"""Tests for orchestrator status_gate (status file + single-pending re-arm)."""

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
    REARM_PENDING_FIELD_NAME,
    REASON_ACTIVE,
    REASON_MISSING_STATUS_FILE,
    REASON_REARM_ALREADY_PENDING,
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
        status_gate.write_status_file(
            status_file_path, RUN_STATUS_ACTIVE, "", is_rearm_pending=False
        )
        is_allowed, reason_code = status_gate.decide_should_reschedule(status_file_path)
        assert is_allowed is True
        assert reason_code == REASON_ACTIVE

    def should_stop_when_status_is_done(self, temporary_directory: Path) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "run-status.json"
        status_gate.write_status_file(
            status_file_path, RUN_STATUS_DONE, "", is_rearm_pending=False
        )
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

    def should_deny_reschedule_when_rearm_already_pending(
        self, temporary_directory: Path
    ) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "run-status.json"
        status_gate.write_status_file(
            status_file_path, RUN_STATUS_ACTIVE, "", is_rearm_pending=True
        )
        is_allowed, reason_code = status_gate.decide_should_reschedule(status_file_path)
        assert is_allowed is False
        assert reason_code == REASON_REARM_ALREADY_PENDING


class TestSetPreservesPending:
    def should_preserve_rearm_pending_when_reasserting_active(
        self, temporary_directory: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "status.json"
        status_gate.write_status_file(
            status_file_path, RUN_STATUS_ACTIVE, "demo", is_rearm_pending=False
        )
        assert status_gate.claim_rearm_slot(status_file_path, "demo")[0] is True
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
                "demo",
            ],
        )
        assert status_gate.main() == EXIT_CODE_SUCCESS
        payload = json.loads(status_file_path.read_text(encoding="utf-8"))
        assert payload[REARM_PENDING_FIELD_NAME] is True
        is_allowed, reason_code = status_gate.decide_should_reschedule(
            status_file_path
        )
        assert is_allowed is False
        assert reason_code == REASON_REARM_ALREADY_PENDING

    def should_clear_rearm_pending_when_setting_done(
        self, temporary_directory: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "status.json"
        status_gate.write_status_file(
            status_file_path, RUN_STATUS_ACTIVE, "", is_rearm_pending=True
        )
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
        payload = json.loads(status_file_path.read_text(encoding="utf-8"))
        assert payload[STATUS_FIELD_NAME] == RUN_STATUS_DONE
        assert payload[REARM_PENDING_FIELD_NAME] is False


class TestBeginClaimRelease:
    def should_claim_rearm_only_once_until_begin_firing(
        self, temporary_directory: Path
    ) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "run-status.json"
        status_gate.write_status_file(
            status_file_path, RUN_STATUS_ACTIVE, "demo", is_rearm_pending=False
        )
        is_claimed, reason_code, payload = status_gate.claim_rearm_slot(
            status_file_path, "demo"
        )
        assert is_claimed is True
        assert payload is not None
        assert payload[REARM_PENDING_FIELD_NAME] is True

        is_claimed_again, second_reason, _second_payload = status_gate.claim_rearm_slot(
            status_file_path, "demo"
        )
        assert is_claimed_again is False
        assert second_reason == REASON_REARM_ALREADY_PENDING

        is_firing, firing_reason, firing_payload = status_gate.begin_firing(
            status_file_path, "demo"
        )
        assert is_firing is True
        assert firing_payload is not None
        assert firing_payload[REARM_PENDING_FIELD_NAME] is False
        assert firing_reason

        is_claimed_after_firing, _claim_reason, after_payload = (
            status_gate.claim_rearm_slot(status_file_path, "demo")
        )
        assert is_claimed_after_firing is True
        assert after_payload is not None
        assert after_payload[REARM_PENDING_FIELD_NAME] is True

    def should_release_rearm_after_failed_schedule(
        self, temporary_directory: Path
    ) -> None:
        status_gate = load_status_gate_module()
        status_file_path = temporary_directory / "run-status.json"
        status_gate.write_status_file(
            status_file_path, RUN_STATUS_ACTIVE, "", is_rearm_pending=False
        )
        assert status_gate.claim_rearm_slot(status_file_path, "")[0] is True
        is_released, reason_code, payload = status_gate.release_rearm_slot(
            status_file_path, ""
        )
        assert is_released is True
        assert payload is not None
        assert payload[REARM_PENDING_FIELD_NAME] is False
        assert reason_code
        is_allowed, allow_reason = status_gate.decide_should_reschedule(
            status_file_path
        )
        assert is_allowed is True
        assert allow_reason == REASON_ACTIVE


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
        assert payload[REARM_PENDING_FIELD_NAME] is False

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
                "claim-rearm",
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
                "claim-rearm",
                "--status-file",
                str(status_file_path),
            ],
        )
        assert status_gate.main() == EXIT_CODE_STOP
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

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "status_gate.py",
                "begin-firing",
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
