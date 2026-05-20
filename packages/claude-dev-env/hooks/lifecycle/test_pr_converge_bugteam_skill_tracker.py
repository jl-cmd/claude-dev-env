"""Unit tests for the pr_converge_bugteam_skill_tracker PreToolUse hook.

Covers the bugteam-only update path: only Skill({skill: "bugteam"}) updates
the invocation fields in $CLAUDE_JOB_DIR/pr-converge-state.json (the file
named by PR_CONVERGE_STATE_FILENAME). qbug, other skills, and missing-state
cases all return exit 0 without modifying state.
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import sys
from typing import Any
from unittest import mock

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_TREE = _HOOK_DIR.parent
for each_path in (str(_HOOK_DIR), str(_HOOKS_TREE)):
    if each_path not in sys.path:
        sys.path.insert(0, each_path)

hook_spec = importlib.util.spec_from_file_location(
    "pr_converge_bugteam_skill_tracker",
    _HOOK_DIR / "pr_converge_bugteam_skill_tracker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

from hooks_constants.pr_converge_bugteam_enforcer_constants import (
    CLAUDE_JOB_DIR_ENV_VAR,
    PR_CONVERGE_STATE_FILENAME,
)

_HEAD_SHA = "abc123def456abc123def456abc123def456abcd"
_TICK_COUNT = 4


def _write_state(state_directory: pathlib.Path, state: dict[str, Any]) -> pathlib.Path:
    state_path = state_directory / PR_CONVERGE_STATE_FILENAME
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path


def _baseline_state() -> dict[str, Any]:
    return {
        "phase": "BUGTEAM",
        "current_head": _HEAD_SHA,
        "tick_count": _TICK_COUNT,
        "bugteam_skill_invoked_at_head": None,
        "bugteam_skill_invoked_at_tick": None,
    }


def _read_state(state_directory: pathlib.Path) -> dict[str, Any]:
    state_path = state_directory / PR_CONVERGE_STATE_FILENAME
    return json.loads(state_path.read_text(encoding="utf-8"))


def _run_main_with_io(input_text: str) -> None:
    with mock.patch("sys.stdin", io.StringIO(input_text)):
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            try:
                hook_module.main()
            except SystemExit:
                pass


def _run_main_capturing_stderr(input_text: str) -> str:
    with mock.patch("sys.stdin", io.StringIO(input_text)):
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            with mock.patch("sys.stderr", new_callable=io.StringIO) as captured_stderr:
                try:
                    hook_module.main()
                except SystemExit:
                    pass
                return captured_stderr.getvalue()


@pytest.fixture()
def claude_job_directory(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    monkeypatch.setenv(CLAUDE_JOB_DIR_ENV_VAR, str(tmp_path))
    return tmp_path


def test_should_record_invocation_when_bugteam_skill_fires(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(claude_job_directory, _baseline_state())
    skill_payload: dict[str, Any] = {
        "tool_name": "Skill",
        "tool_input": {"skill": "bugteam", "args": "https://github.com/o/r/pull/1"},
    }
    _run_main_with_io(json.dumps(skill_payload))
    updated_state = _read_state(claude_job_directory)
    assert updated_state["bugteam_skill_invoked_at_head"] == _HEAD_SHA
    assert updated_state["bugteam_skill_invoked_at_tick"] == _TICK_COUNT


def test_should_not_record_invocation_when_qbug_skill_fires(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(claude_job_directory, _baseline_state())
    qbug_payload: dict[str, Any] = {
        "tool_name": "Skill",
        "tool_input": {"skill": "qbug"},
    }
    _run_main_with_io(json.dumps(qbug_payload))
    updated_state = _read_state(claude_job_directory)
    assert updated_state["bugteam_skill_invoked_at_head"] is None
    assert updated_state["bugteam_skill_invoked_at_tick"] is None


def test_should_ignore_unrelated_skills(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(claude_job_directory, _baseline_state())
    other_payload: dict[str, Any] = {
        "tool_name": "Skill",
        "tool_input": {"skill": "agent-prompt"},
    }
    _run_main_with_io(json.dumps(other_payload))
    updated_state = _read_state(claude_job_directory)
    assert updated_state["bugteam_skill_invoked_at_head"] is None


def test_should_ignore_non_skill_tools(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(claude_job_directory, _baseline_state())
    agent_payload: dict[str, Any] = {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "clean-coder", "prompt": "fix this"},
    }
    _run_main_with_io(json.dumps(agent_payload))
    updated_state = _read_state(claude_job_directory)
    assert updated_state["bugteam_skill_invoked_at_head"] is None


def test_should_no_op_when_state_file_absent(
    claude_job_directory: pathlib.Path,
) -> None:
    skill_payload: dict[str, Any] = {
        "tool_name": "Skill",
        "tool_input": {"skill": "bugteam"},
    }
    _run_main_with_io(json.dumps(skill_payload))
    assert not (claude_job_directory / PR_CONVERGE_STATE_FILENAME).exists()


def test_should_no_op_when_state_json_is_malformed(
    claude_job_directory: pathlib.Path,
) -> None:
    state_path = claude_job_directory / PR_CONVERGE_STATE_FILENAME
    state_path.write_text("{not valid json", encoding="utf-8")
    skill_payload: dict[str, Any] = {
        "tool_name": "Skill",
        "tool_input": {"skill": "bugteam"},
    }
    _run_main_with_io(json.dumps(skill_payload))
    assert state_path.read_text(encoding="utf-8") == "{not valid json"


def test_should_preserve_other_state_fields_on_update(
    claude_job_directory: pathlib.Path,
) -> None:
    baseline_state = _baseline_state()
    baseline_state["bugbot_clean_at"] = _HEAD_SHA
    baseline_state["copilot_wait_count"] = 2
    _write_state(claude_job_directory, baseline_state)
    skill_payload: dict[str, Any] = {
        "tool_name": "Skill",
        "tool_input": {"skill": "bugteam"},
    }
    _run_main_with_io(json.dumps(skill_payload))
    updated_state = _read_state(claude_job_directory)
    assert updated_state["bugbot_clean_at"] == _HEAD_SHA
    assert updated_state["copilot_wait_count"] == 2
    assert updated_state["bugteam_skill_invoked_at_head"] == _HEAD_SHA


def test_should_no_op_when_claude_job_dir_env_var_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CLAUDE_JOB_DIR_ENV_VAR, raising=False)
    skill_payload: dict[str, Any] = {
        "tool_name": "Skill",
        "tool_input": {"skill": "bugteam"},
    }
    _run_main_with_io(json.dumps(skill_payload))


def test_should_no_op_when_payload_is_malformed_json(
    claude_job_directory: pathlib.Path,
) -> None:
    baseline_state = _baseline_state()
    _write_state(claude_job_directory, baseline_state)
    _run_main_with_io("not valid json {{{")
    updated_state = _read_state(claude_job_directory)
    assert updated_state["bugteam_skill_invoked_at_head"] is None


def test_should_leave_state_unchanged_when_current_head_is_missing(
    claude_job_directory: pathlib.Path,
) -> None:
    state_without_head = _baseline_state()
    del state_without_head["current_head"]
    _write_state(claude_job_directory, state_without_head)
    skill_payload: dict[str, Any] = {
        "tool_name": "Skill",
        "tool_input": {"skill": "bugteam"},
    }
    captured_stderr = _run_main_capturing_stderr(json.dumps(skill_payload))
    updated_state = _read_state(claude_job_directory)
    assert "current_head" not in updated_state
    assert updated_state.get("bugteam_skill_invoked_at_head") is None
    assert updated_state.get("bugteam_skill_invoked_at_tick") is None
    assert "current_head or tick_count" in captured_stderr


def test_should_leave_state_unchanged_when_tick_count_is_missing(
    claude_job_directory: pathlib.Path,
) -> None:
    state_without_tick = _baseline_state()
    del state_without_tick["tick_count"]
    _write_state(claude_job_directory, state_without_tick)
    skill_payload: dict[str, Any] = {
        "tool_name": "Skill",
        "tool_input": {"skill": "bugteam"},
    }
    captured_stderr = _run_main_capturing_stderr(json.dumps(skill_payload))
    updated_state = _read_state(claude_job_directory)
    assert "tick_count" not in updated_state
    assert updated_state.get("bugteam_skill_invoked_at_head") is None
    assert updated_state.get("bugteam_skill_invoked_at_tick") is None
    assert "current_head or tick_count" in captured_stderr


def test_should_preserve_prior_stamp_when_current_head_becomes_missing(
    claude_job_directory: pathlib.Path,
) -> None:
    prior_head = "feedface0000feedface0000feedface0000feed"
    prior_tick = 3
    state_with_prior_stamp = _baseline_state()
    state_with_prior_stamp["bugteam_skill_invoked_at_head"] = prior_head
    state_with_prior_stamp["bugteam_skill_invoked_at_tick"] = prior_tick
    del state_with_prior_stamp["current_head"]
    _write_state(claude_job_directory, state_with_prior_stamp)
    skill_payload: dict[str, Any] = {
        "tool_name": "Skill",
        "tool_input": {"skill": "bugteam"},
    }
    _run_main_capturing_stderr(json.dumps(skill_payload))
    updated_state = _read_state(claude_job_directory)
    assert updated_state["bugteam_skill_invoked_at_head"] == prior_head
    assert updated_state["bugteam_skill_invoked_at_tick"] == prior_tick


def test_should_skip_atomic_write_when_state_missing_required_fields(
    claude_job_directory: pathlib.Path,
) -> None:
    state_without_head = _baseline_state()
    del state_without_head["current_head"]
    _write_state(claude_job_directory, state_without_head)
    skill_payload: dict[str, Any] = {
        "tool_name": "Skill",
        "tool_input": {"skill": "bugteam"},
    }
    with mock.patch.object(hook_module, "_atomic_write_state") as patched_atomic_write:
        with mock.patch("sys.stdin", io.StringIO(json.dumps(skill_payload))):
            with mock.patch("sys.stdout", new_callable=io.StringIO):
                with mock.patch("sys.stderr", new_callable=io.StringIO):
                    try:
                        hook_module.main()
                    except SystemExit:
                        pass
        assert patched_atomic_write.call_count == 0
