"""Tests for orchestrator_refresh_reschedule_gate PreToolUse hook."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

BLOCKING_DIRECTORY = Path(__file__).resolve().parent
HOOKS_DIRECTORY = BLOCKING_DIRECTORY.parent
if str(HOOKS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIRECTORY))

SKILL_SCRIPTS = HOOKS_DIRECTORY.parent / "skills" / "orchestrator" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from status_gate_constants.config.constants import RUN_STATUS_ACTIVE, RUN_STATUS_DONE  # noqa: E402
from status_gate import write_status_file  # noqa: E402


def load_gate_module() -> ModuleType:
    module_path = BLOCKING_DIRECTORY / "orchestrator_refresh_reschedule_gate.py"
    spec = importlib.util.spec_from_file_location(
        "orchestrator_refresh_reschedule_gate",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    gate_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = gate_module
    spec.loader.exec_module(gate_module)
    return gate_module


def run_main_with_payload(
    gate_module: ModuleType,
    payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[int, str]:
    stdin_buffer = io.StringIO(json.dumps(payload))
    stdout_buffer = io.StringIO()
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    monkeypatch.setattr(sys, "stdout", stdout_buffer)
    exit_code = 0
    try:
        gate_module.main()
    except SystemExit as system_exit:
        exit_code = int(system_exit.code or 0)
    return exit_code, stdout_buffer.getvalue()


class TestOrchestratorRefreshRescheduleGate:
    def should_allow_when_status_is_active(
        self,
        temporary_directory: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        status_file_path = temporary_directory / "status.json"
        write_status_file(status_file_path, RUN_STATUS_ACTIVE, "", is_rearm_pending=False)
        monkeypatch.setenv("ORCHESTRATOR_RUN_STATUS_FILE", str(status_file_path))
        gate_module = load_gate_module()
        payload = {
            "tool_name": "ScheduleWakeup",
            "tool_input": {"prompt": "/orchestrator-refresh", "delaySeconds": 1200},
            "cwd": str(temporary_directory),
        }
        exit_code, stdout_text = run_main_with_payload(
            gate_module, payload, monkeypatch
        )
        assert exit_code == 0
        assert stdout_text == ""

    def should_deny_when_status_is_done(
        self,
        temporary_directory: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        status_file_path = temporary_directory / "status.json"
        write_status_file(status_file_path, RUN_STATUS_DONE, "", is_rearm_pending=False)
        monkeypatch.setenv("ORCHESTRATOR_RUN_STATUS_FILE", str(status_file_path))
        gate_module = load_gate_module()
        payload = {
            "tool_name": "ScheduleWakeup",
            "tool_input": {"prompt": "/orchestrator-refresh re-arm"},
            "cwd": str(temporary_directory),
        }
        exit_code, stdout_text = run_main_with_payload(
            gate_module, payload, monkeypatch
        )
        assert exit_code == 0
        denial = json.loads(stdout_text)
        assert denial["hookSpecificOutput"]["permissionDecision"] == "deny"

    def should_deny_when_status_file_missing(
        self,
        temporary_directory: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        missing_path = temporary_directory / "nope.json"
        monkeypatch.setenv("ORCHESTRATOR_RUN_STATUS_FILE", str(missing_path))
        gate_module = load_gate_module()
        payload = {
            "tool_name": "ScheduleWakeup",
            "tool_input": {"prompt": "/orchestrator-refresh now"},
            "cwd": str(temporary_directory),
        }
        _exit_code, stdout_text = run_main_with_payload(
            gate_module, payload, monkeypatch
        )
        denial = json.loads(stdout_text)
        assert denial["hookSpecificOutput"]["permissionDecision"] == "deny"

    def should_deny_when_rearm_slot_already_pending(
        self,
        temporary_directory: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        status_file_path = temporary_directory / "status.json"
        write_status_file(
            status_file_path, RUN_STATUS_ACTIVE, "", is_rearm_pending=True
        )
        monkeypatch.setenv("ORCHESTRATOR_RUN_STATUS_FILE", str(status_file_path))
        gate_module = load_gate_module()
        payload = {
            "tool_name": "ScheduleWakeup",
            "tool_input": {"prompt": "/orchestrator-refresh", "delaySeconds": 1200},
            "cwd": str(temporary_directory),
        }
        _exit_code, stdout_text = run_main_with_payload(
            gate_module, payload, monkeypatch
        )
        denial = json.loads(stdout_text)
        assert denial["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "rearm_already_pending" in denial["hookSpecificOutput"][
            "permissionDecisionReason"
        ]

    def should_always_deny_cron_create_for_orchestrator_refresh(
        self,
        temporary_directory: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        status_file_path = temporary_directory / "status.json"
        write_status_file(status_file_path, RUN_STATUS_ACTIVE, "", is_rearm_pending=False)
        monkeypatch.setenv("ORCHESTRATOR_RUN_STATUS_FILE", str(status_file_path))
        gate_module = load_gate_module()
        payload = {
            "tool_name": "CronCreate",
            "tool_input": {"prompt": "/orchestrator-refresh"},
            "cwd": str(temporary_directory),
        }
        _exit_code, stdout_text = run_main_with_payload(
            gate_module, payload, monkeypatch
        )
        denial = json.loads(stdout_text)
        assert denial["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "cron_create_forbidden" in denial["hookSpecificOutput"][
            "permissionDecisionReason"
        ]

    def should_ignore_unrelated_schedule_prompts(
        self,
        temporary_directory: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        gate_module = load_gate_module()
        payload = {
            "tool_name": "ScheduleWakeup",
            "tool_input": {"prompt": "/pr-converge"},
            "cwd": str(temporary_directory),
        }
        exit_code, stdout_text = run_main_with_payload(
            gate_module, payload, monkeypatch
        )
        assert exit_code == 0
        assert stdout_text == ""

    def should_ignore_prose_mention_of_orchestrator_refresh(
        self,
        temporary_directory: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        gate_module = load_gate_module()
        payload = {
            "tool_name": "ScheduleWakeup",
            "tool_input": {
                "prompt": "See docs about /orchestrator-refresh for later"
            },
            "cwd": str(temporary_directory),
        }
        exit_code, stdout_text = run_main_with_payload(
            gate_module, payload, monkeypatch
        )
        assert exit_code == 0
        assert stdout_text == ""

    def should_allow_when_prompt_carries_run_slug_for_scoped_status(
        self,
        temporary_directory: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        run_slug = "demo-run"
        status_file_path = temporary_directory.joinpath(
            "docs", "plans", run_slug, ".orchestrator-run-status.json"
        )
        write_status_file(status_file_path, RUN_STATUS_ACTIVE, run_slug, is_rearm_pending=False)
        monkeypatch.delenv("ORCHESTRATOR_RUN_STATUS_FILE", raising=False)
        gate_module = load_gate_module()
        payload = {
            "tool_name": "ScheduleWakeup",
            "tool_input": {
                "prompt": f"/orchestrator-refresh --run-slug {run_slug}"
            },
            "cwd": str(temporary_directory),
        }
        exit_code, stdout_text = run_main_with_payload(
            gate_module, payload, monkeypatch
        )
        assert exit_code == 0
        assert stdout_text == ""


@pytest.fixture
def temporary_directory(tmp_path: Path) -> Path:
    return tmp_path
