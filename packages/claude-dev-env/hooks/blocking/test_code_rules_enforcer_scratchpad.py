"""Tests for the session-scratchpad exemption wired into code_rules_enforcer.main."""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType

import pytest

_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)
from blocking import _path_setup  # noqa: F401

from code_rules_enforcer_test_support import run_serialized_payload_entrypoint

ENFORCER_PATH = Path(__file__).parent / "code_rules_enforcer.py"
FIXED_USER_ID = 6070
WORKING_DIRECTORY = "/home/user/project"
SESSION_ID = "enforcer-session-654"
VIOLATING_CONTENT = "def compute():\n    data = 42\n    return data\n"


def _load_enforcer() -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        "code_rules_enforcer_scratchpad_under_test", ENFORCER_PATH
    )
    assert module_spec is not None and module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


_ENFORCER = _load_enforcer()


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
        "tool_input": {"file_path": str(target), "content": VIOLATING_CONTENT},
    }


def _run_main(payload_by_key: dict[str, object]) -> tuple[int | None, str]:
    captured_stdout, exit_code = run_serialized_payload_entrypoint(
        _ENFORCER.main, json.dumps(payload_by_key)
    )
    return exit_code, captured_stdout


def _decision_from(stdout_text: str) -> str | None:
    if not stdout_text.strip():
        return None
    parsed = json.loads(stdout_text)
    return parsed.get("hookSpecificOutput", {}).get("permissionDecision")


def test_scratchpad_write_is_exempt_from_code_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratchpad_directory = _install_scratchpad_signals(monkeypatch, tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", "1")
    throwaway_script = scratchpad_directory / "one_off_probe.py"

    exit_code, stdout_text = _run_main(_write_payload(throwaway_script))

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

    exit_code, stdout_text = _run_main(_write_payload(production_module))

    assert exit_code == 0
    assert _decision_from(stdout_text) == "deny"
