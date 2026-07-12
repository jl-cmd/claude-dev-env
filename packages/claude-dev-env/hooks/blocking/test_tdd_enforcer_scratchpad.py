"""Tests for the session-scratchpad exemption wired into tdd_enforcer.main."""

import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType

import pytest

TDD_ENFORCER_PATH = Path(__file__).parent / "tdd_enforcer.py"
FIXED_USER_ID = 5150
WORKING_DIRECTORY = "/home/user/project"
SESSION_ID = "tdd-session-987"
PRODUCTION_CONTENT = "def fulfill_order():\n    return True\n"


def _load_tdd_enforcer() -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        "tdd_enforcer_scratchpad_under_test", TDD_ENFORCER_PATH
    )
    assert module_spec is not None and module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


_TDD_ENFORCER = _load_tdd_enforcer()


def _install_scratchpad_signals(monkeypatch: pytest.MonkeyPatch, temporary_root: Path) -> Path:
    monkeypatch.setattr(os, "getuid", lambda: FIXED_USER_ID, raising=False)
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temporary_root))
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


def _write_payload(target: Path) -> dict[str, object]:
    return {
        "tool_name": "Write",
        "cwd": WORKING_DIRECTORY,
        "session_id": SESSION_ID,
        "tool_input": {"file_path": str(target), "content": PRODUCTION_CONTENT},
    }


def _run_main(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
) -> tuple[int | None, str]:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)
    exit_code: int | None = None
    try:
        _TDD_ENFORCER.main()
    except SystemExit as raised_exit:
        raw_code = raised_exit.code
        exit_code = raw_code if isinstance(raw_code, int) else None
    return exit_code, captured_stdout.getvalue()


def _decision_from(stdout_text: str) -> str | None:
    if not stdout_text.strip():
        return None
    parsed = json.loads(stdout_text)
    return parsed.get("hookSpecificOutput", {}).get("permissionDecision")


def test_scratchpad_production_write_is_exempt_from_tdd_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratchpad_directory = _install_scratchpad_signals(monkeypatch, tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", "1")
    throwaway_script = scratchpad_directory / "one_off_probe.py"

    exit_code, stdout_text = _run_main(monkeypatch, _write_payload(throwaway_script))

    assert exit_code == 0
    assert _decision_from(stdout_text) != "deny"


def test_identical_non_scratchpad_write_is_still_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_scratchpad_signals(monkeypatch, tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", "1")
    outside_directory = tmp_path / "project" / "orders"
    outside_directory.mkdir(parents=True)
    production_module = outside_directory / "one_off_probe.py"

    exit_code, stdout_text = _run_main(monkeypatch, _write_payload(production_module))

    assert exit_code == 0
    assert _decision_from(stdout_text) == "deny"
