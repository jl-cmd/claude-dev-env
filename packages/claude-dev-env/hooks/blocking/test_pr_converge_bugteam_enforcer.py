"""Unit tests for the pr_converge_bugteam_enforcer PreToolUse hook.

Covers the Step 5 BUGTEAM contract: Agent({subagent_type: "clean-coder"})
calls that look like audit substitutes are blocked when
$CLAUDE_JOB_DIR/pr-converge-state.json (named by PR_CONVERGE_STATE_FILENAME)
shows phase=BUGTEAM and the formal Skill({skill: "bugteam"}) has not
registered at the current HEAD and tick. qbug is explicitly NOT a substitute.
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
    "pr_converge_bugteam_enforcer",
    _HOOK_DIR / "pr_converge_bugteam_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

from config.pr_converge_bugteam_enforcer_constants import (
    BUGTEAM_PHASE,
    CLAUDE_JOB_DIR_ENV_VAR,
    PR_CONVERGE_STATE_FILENAME,
)

_HEAD_SHA_CURRENT = "abc123def456abc123def456abc123def456abcd"
_HEAD_SHA_STALE = "deadbeef0000deadbeef0000deadbeef0000dead"
_TICK_CURRENT = 7
_AUDIT_PROMPT = "Run the bugteam audit and report findings against the A-J categories."
_FIX_ONLY_PROMPT = "Fix the failing test in tests/test_widget.py by adding a guard clause."


def _write_state(state_directory: pathlib.Path, state: dict[str, Any]) -> pathlib.Path:
    state_path = state_directory / PR_CONVERGE_STATE_FILENAME
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path


def _bugteam_phase_state(**overrides: Any) -> dict[str, Any]:
    baseline_state: dict[str, Any] = {
        "phase": BUGTEAM_PHASE,
        "current_head": _HEAD_SHA_CURRENT,
        "tick_count": _TICK_CURRENT,
        "bugteam_skill_invoked_at_head": None,
        "bugteam_skill_invoked_at_tick": None,
    }
    baseline_state.update(overrides)
    return baseline_state


def _clean_coder_audit_payload(prompt: str = _AUDIT_PROMPT) -> dict[str, Any]:
    return {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": "clean-coder",
            "prompt": prompt,
            "description": "Audit the PR",
        },
    }


def _run_main_with_io(input_text: str) -> str:
    with mock.patch("sys.stdin", io.StringIO(input_text)):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as captured_stdout:
            try:
                hook_module.main()
            except SystemExit:
                pass
            return captured_stdout.getvalue()


@pytest.fixture()
def claude_job_directory(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    monkeypatch.setenv(CLAUDE_JOB_DIR_ENV_VAR, str(tmp_path))
    return tmp_path


def test_should_allow_when_state_file_absent(claude_job_directory: pathlib.Path) -> None:
    payload_text = json.dumps(_clean_coder_audit_payload())
    captured_output = _run_main_with_io(payload_text)
    assert captured_output == ""


def test_should_allow_when_phase_not_bugteam(claude_job_directory: pathlib.Path) -> None:
    _write_state(claude_job_directory, _bugteam_phase_state(phase="BUGBOT"))
    payload_text = json.dumps(_clean_coder_audit_payload())
    captured_output = _run_main_with_io(payload_text)
    assert captured_output == ""


def test_should_allow_when_subagent_type_not_clean_coder(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(claude_job_directory, _bugteam_phase_state())
    explore_payload: dict[str, Any] = {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "Explore", "prompt": _AUDIT_PROMPT},
    }
    captured_output = _run_main_with_io(json.dumps(explore_payload))
    assert captured_output == ""


def test_should_allow_when_prompt_lacks_audit_keywords(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(claude_job_directory, _bugteam_phase_state())
    payload_text = json.dumps(_clean_coder_audit_payload(prompt=_FIX_ONLY_PROMPT))
    captured_output = _run_main_with_io(payload_text)
    assert captured_output == ""


def test_should_block_when_clean_coder_audit_without_bugteam_skill_invocation(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(claude_job_directory, _bugteam_phase_state())
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    deny_payload = json.loads(captured_output)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "bugteam-enforcer" in deny_payload["hookSpecificOutput"]["permissionDecisionReason"]


def test_should_allow_after_bugteam_skill_invoked_at_current_head_and_tick(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(
        claude_job_directory,
        _bugteam_phase_state(
            bugteam_skill_invoked_at_head=_HEAD_SHA_CURRENT,
            bugteam_skill_invoked_at_tick=_TICK_CURRENT,
        ),
    )
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    assert captured_output == ""


def test_should_block_when_bugteam_skill_invocation_is_stale_head(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(
        claude_job_directory,
        _bugteam_phase_state(
            bugteam_skill_invoked_at_head=_HEAD_SHA_STALE,
            bugteam_skill_invoked_at_tick=_TICK_CURRENT,
        ),
    )
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    deny_payload = json.loads(captured_output)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_should_block_when_qbug_was_invoked_but_not_bugteam(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(
        claude_job_directory,
        _bugteam_phase_state(
            bugteam_skill_invoked_at_head=None,
            bugteam_skill_invoked_at_tick=None,
        ),
    )
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    deny_payload = json.loads(captured_output)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_should_block_when_bugteam_invoked_at_current_head_but_previous_tick(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(
        claude_job_directory,
        _bugteam_phase_state(
            bugteam_skill_invoked_at_head=_HEAD_SHA_CURRENT,
            bugteam_skill_invoked_at_tick=_TICK_CURRENT - 1,
        ),
    )
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    deny_payload = json.loads(captured_output)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_should_block_when_invoked_head_is_non_string_type(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(
        claude_job_directory,
        _bugteam_phase_state(
            bugteam_skill_invoked_at_head=42,
            bugteam_skill_invoked_at_tick=_TICK_CURRENT,
        ),
    )
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    deny_payload = json.loads(captured_output)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_should_block_when_current_head_is_non_string_type(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(
        claude_job_directory,
        _bugteam_phase_state(
            current_head=42,
            bugteam_skill_invoked_at_head=_HEAD_SHA_CURRENT,
            bugteam_skill_invoked_at_tick=_TICK_CURRENT,
        ),
    )
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    deny_payload = json.loads(captured_output)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_should_block_when_invoked_tick_is_string_type(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(
        claude_job_directory,
        _bugteam_phase_state(
            bugteam_skill_invoked_at_head=_HEAD_SHA_CURRENT,
            bugteam_skill_invoked_at_tick="7",
        ),
    )
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    deny_payload = json.loads(captured_output)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_should_block_when_current_tick_is_string_type(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(
        claude_job_directory,
        _bugteam_phase_state(
            tick_count="7",
            bugteam_skill_invoked_at_head=_HEAD_SHA_CURRENT,
            bugteam_skill_invoked_at_tick=_TICK_CURRENT,
        ),
    )
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    deny_payload = json.loads(captured_output)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_should_block_when_invoked_tick_is_bool_type(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(
        claude_job_directory,
        _bugteam_phase_state(
            tick_count=1,
            bugteam_skill_invoked_at_head=_HEAD_SHA_CURRENT,
            bugteam_skill_invoked_at_tick=True,
        ),
    )
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    deny_payload = json.loads(captured_output)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_should_block_when_current_tick_is_bool_type(
    claude_job_directory: pathlib.Path,
) -> None:
    _write_state(
        claude_job_directory,
        _bugteam_phase_state(
            tick_count=True,
            bugteam_skill_invoked_at_head=_HEAD_SHA_CURRENT,
            bugteam_skill_invoked_at_tick=1,
        ),
    )
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    deny_payload = json.loads(captured_output)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_should_allow_when_claude_job_dir_env_var_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CLAUDE_JOB_DIR_ENV_VAR, raising=False)
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    assert captured_output == ""


def test_should_allow_when_state_json_is_malformed(
    claude_job_directory: pathlib.Path,
) -> None:
    state_path = claude_job_directory / PR_CONVERGE_STATE_FILENAME
    state_path.write_text("{not valid json", encoding="utf-8")
    captured_output = _run_main_with_io(json.dumps(_clean_coder_audit_payload()))
    assert captured_output == ""


def test_should_allow_when_payload_is_malformed_json() -> None:
    captured_output = _run_main_with_io("not valid json {{{")
    assert captured_output == ""
