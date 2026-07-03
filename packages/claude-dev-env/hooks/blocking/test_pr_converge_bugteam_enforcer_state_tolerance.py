"""Unit tests: persistent-agent state keys leave both pr-converge hooks unchanged.

pr-converge-state.json carries `agents_session_id` and `persistent_agents`
(the persistent per-step agent map with a `fix_executor` entry). Neither the
enforcer (`pr_converge_bugteam_enforcer`) nor the tracker
(`pr_converge_bugteam_skill_tracker`) reads these keys, so their allow/block
decisions and stamped fields match a state file without them, and the tracker
preserves the keys unchanged on its stamp write.
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import sys
from types import ModuleType
from typing import Any
from unittest import mock

import pytest

_BLOCKING_DIR = pathlib.Path(__file__).parent
_HOOKS_TREE = _BLOCKING_DIR.parent
_LIFECYCLE_DIR = _HOOKS_TREE / "lifecycle"
for each_path in (str(_BLOCKING_DIR), str(_HOOKS_TREE)):
    if each_path not in sys.path:
        sys.path.insert(0, each_path)


def _load_hook_module(module_name: str, module_path: pathlib.Path) -> ModuleType:
    hook_spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert hook_spec is not None
    assert hook_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(hook_spec)
    hook_spec.loader.exec_module(loaded_module)
    return loaded_module


enforcer_module = _load_hook_module(
    "pr_converge_bugteam_enforcer_state_tolerance_target",
    _BLOCKING_DIR / "pr_converge_bugteam_enforcer.py",
)
tracker_module = _load_hook_module(
    "pr_converge_bugteam_skill_tracker_state_tolerance_target",
    _LIFECYCLE_DIR / "pr_converge_bugteam_skill_tracker.py",
)

from hooks_constants.pr_converge_bugteam_enforcer_constants import (
    BUGTEAM_PHASE,
    CLAUDE_JOB_DIR_ENV_VAR,
    PR_CONVERGE_STATE_FILENAME,
)

_HEAD_SHA_CURRENT = "abc123def456abc123def456abc123def456abcd"
_TICK_CURRENT = 7
_AUDIT_PROMPT = "Run the bugteam audit and report findings against the A-J categories."
_AGENTS_SESSION_ID = "session-0123456789abcdef"
_FIX_EXECUTOR_AGENT_ID = "prc-fix-42"


def _persistent_agent_state_keys() -> dict[str, Any]:
    return {
        "agents_session_id": _AGENTS_SESSION_ID,
        "persistent_agents": {
            "fix_executor": {
                "agent_id": _FIX_EXECUTOR_AGENT_ID,
                "created_tick": 2,
                "last_used_tick": 6,
            }
        },
    }


def _bugteam_phase_state(**overrides: Any) -> dict[str, Any]:
    baseline_state: dict[str, Any] = {
        "phase": BUGTEAM_PHASE,
        "current_head": _HEAD_SHA_CURRENT,
        "tick_count": _TICK_CURRENT,
        "bugteam_skill_invoked_at_head": None,
        "bugteam_skill_invoked_at_tick": None,
    }
    baseline_state.update(_persistent_agent_state_keys())
    baseline_state.update(overrides)
    return baseline_state


def _write_state(state_directory: pathlib.Path, state: dict[str, Any]) -> pathlib.Path:
    state_path = state_directory / PR_CONVERGE_STATE_FILENAME
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path


def _read_state(state_directory: pathlib.Path) -> dict[str, Any]:
    state_path = state_directory / PR_CONVERGE_STATE_FILENAME
    return json.loads(state_path.read_text(encoding="utf-8"))


def _clean_coder_audit_payload() -> dict[str, Any]:
    return {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": "clean-coder",
            "prompt": _AUDIT_PROMPT,
            "description": "Audit the PR",
        },
    }


def _bugteam_skill_payload() -> dict[str, Any]:
    return {
        "tool_name": "Skill",
        "tool_input": {"skill": "bugteam", "args": "https://github.com/o/r/pull/1"},
    }


def _run_enforcer_main_with_io(input_text: str) -> str:
    with mock.patch("sys.stdin", io.StringIO(input_text)):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as captured_stdout:
            try:
                enforcer_module.main()
            except SystemExit:
                pass
            return captured_stdout.getvalue()


def _run_tracker_main_with_io(input_text: str) -> None:
    with mock.patch("sys.stdin", io.StringIO(input_text)):
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            with mock.patch("sys.stderr", new_callable=io.StringIO):
                try:
                    tracker_module.main()
                except SystemExit:
                    pass


@pytest.fixture()
def claude_job_directory(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    monkeypatch.setenv(CLAUDE_JOB_DIR_ENV_VAR, str(tmp_path))
    return tmp_path


def test_should_block_enforcer_when_persistent_agent_keys_present_without_skill(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(claude_job_directory, _bugteam_phase_state())
    captured_output = _run_enforcer_main_with_io(json.dumps(_clean_coder_audit_payload()))
    deny_payload = json.loads(captured_output)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_should_allow_enforcer_when_persistent_agent_keys_present_with_skill_recorded(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(
        claude_job_directory,
        _bugteam_phase_state(
            bugteam_skill_invoked_at_head=_HEAD_SHA_CURRENT,
            bugteam_skill_invoked_at_tick=_TICK_CURRENT,
        ),
    )
    captured_output = _run_enforcer_main_with_io(json.dumps(_clean_coder_audit_payload()))
    assert captured_output == ""


def test_should_stamp_tracker_fields_when_persistent_agent_keys_present(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(claude_job_directory, _bugteam_phase_state())
    _run_tracker_main_with_io(json.dumps(_bugteam_skill_payload()))
    updated_state = _read_state(claude_job_directory)
    assert updated_state["bugteam_skill_invoked_at_head"] == _HEAD_SHA_CURRENT
    assert updated_state["bugteam_skill_invoked_at_tick"] == _TICK_CURRENT


def test_should_preserve_persistent_agent_keys_on_tracker_stamp_write(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(claude_job_directory, _bugteam_phase_state())
    _run_tracker_main_with_io(json.dumps(_bugteam_skill_payload()))
    updated_state = _read_state(claude_job_directory)
    assert updated_state["agents_session_id"] == _AGENTS_SESSION_ID
    assert updated_state["persistent_agents"] == _persistent_agent_state_keys()["persistent_agents"]
