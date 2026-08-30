"""Behavior tests for the Codex Luna fast-mode spawn gate."""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import subprocess
import sys
from typing import Any
from unittest import mock

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_TREE = _HOOK_DIR.parent
for each_path in (str(_HOOK_DIR), str(_HOOKS_TREE)):
    if each_path not in sys.path:
        sys.path.insert(0, each_path)

hook_spec = importlib.util.spec_from_file_location(
    "luna_fast_mode_gate",
    _HOOK_DIR / "luna_fast_mode_gate.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

from hooks_constants.luna_fast_mode_gate_constants import (  # noqa: E402
    AGENT_TOOL_NAME,
    CALLING_HOOK_NAME,
    CODEX_AGENT_TOOL_NAME,
    FAST_SERVICE_TIER,
    TASK_TOOL_NAME,
)

_MODEL_ID = "gpt-5.6-luna"
_NON_LUNA_MODEL_ID = "gpt-5.6-sol"
_UNRELATED_TOOL_NAME = "Write"
_SERVICE_TIER_FIELD_NAME = "service_tier"
_MODEL_FIELD_NAME = "model"
_DENY_DECISION = "deny"


def _spawn_payload(
    *,
    tool_name: str = AGENT_TOOL_NAME,
    model: object = _MODEL_ID,
    service_tier: object = None,
    include_service_tier: bool = True,
) -> dict[str, Any]:
    """Build one PreToolUse payload for a spawn surface."""
    tool_input: dict[str, object] = {
        _MODEL_FIELD_NAME: model,
    }
    if include_service_tier:
        tool_input[_SERVICE_TIER_FIELD_NAME] = service_tier
    return {"tool_name": tool_name, "tool_input": tool_input}


def _run_main(payload: object) -> str:
    """Run the production hook and return its stdout."""
    with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as captured_stdout:
            try:
                hook_module.main()
            except SystemExit:
                pass
            return captured_stdout.getvalue()


def _decision(payload: object) -> str:
    """Return the hook decision for a payload."""
    return json.loads(_run_main(payload))["hookSpecificOutput"]["permissionDecision"]


def test_blocks_luna_without_fast_for_headless_and_in_session_surfaces() -> None:
    all_tool_names = (AGENT_TOOL_NAME, TASK_TOOL_NAME, CODEX_AGENT_TOOL_NAME)
    for each_tool_name in all_tool_names:
        payload = _spawn_payload(tool_name=each_tool_name, service_tier="flex")
        assert _decision(payload) == _DENY_DECISION


def test_allows_luna_with_exact_fast_service_tier() -> None:
    for each_tool_name in (AGENT_TOOL_NAME, TASK_TOOL_NAME, CODEX_AGENT_TOOL_NAME):
        payload = _spawn_payload(
            tool_name=each_tool_name,
            service_tier=FAST_SERVICE_TIER,
        )
        assert _run_main(payload) == ""


def test_blocks_missing_and_non_string_service_tier() -> None:
    assert _decision(_spawn_payload(include_service_tier=False)) == _DENY_DECISION
    assert _decision(_spawn_payload(service_tier=None)) == _DENY_DECISION
    assert _decision(_spawn_payload(service_tier=True)) == _DENY_DECISION


def test_blocks_default_and_wrong_case_fast_service_tiers() -> None:
    assert _decision(_spawn_payload(service_tier="default")) == _DENY_DECISION
    assert _decision(_spawn_payload(service_tier="FAST")) == _DENY_DECISION


def test_allows_non_luna_and_unrelated_tool_payloads() -> None:
    assert _run_main(_spawn_payload(model=_NON_LUNA_MODEL_ID)) == ""
    assert _run_main(
        _spawn_payload(tool_name=_UNRELATED_TOOL_NAME, service_tier="flex")
    ) == ""


def test_recognizes_case_insensitive_luna_model_segments() -> None:
    assert _decision(_spawn_payload(model="GPT-5.6-LUNA", service_tier="flex")) == (
        _DENY_DECISION
    )
    assert _run_main(_spawn_payload(model="gpt-5.6-lunacy", service_tier="flex")) == ""


def test_malformed_outer_payload_allows() -> None:
    assert _run_main({"tool_name": AGENT_TOOL_NAME}) == ""
    assert _run_main({"tool_name": AGENT_TOOL_NAME, "tool_input": []}) == ""
    assert _run_main("not an object") == ""
    assert _run_main({"tool_name": AGENT_TOOL_NAME, "tool_input": {_MODEL_FIELD_NAME: 7}}) == ""


def test_deny_payload_and_log_do_not_include_a_prompt() -> None:
    payload = _spawn_payload(service_tier="default")
    with mock.patch.object(hook_module, "log_hook_block") as recorded_block:
        output = _run_main(payload)
    parsed_output = json.loads(output)
    assert parsed_output["hookSpecificOutput"]["permissionDecision"] == _DENY_DECISION
    assert recorded_block.call_args.kwargs["calling_hook_name"] == CALLING_HOOK_NAME
    assert "prompt" not in recorded_block.call_args.kwargs["offending_input_preview"]


def test_hooks_json_registers_all_spawn_surfaces() -> None:
    hooks_configuration = json.loads(
        (_HOOKS_TREE / "hooks.json").read_text(encoding="utf-8")
    )
    matching_groups = [
        each_group
        for each_group in hooks_configuration["hooks"]["PreToolUse"]
        if CALLING_HOOK_NAME
        in " ".join(each_hook["command"] for each_hook in each_group["hooks"])
    ]
    assert len(matching_groups) == 1
    assert matching_groups[0]["matcher"] == (
        f"{AGENT_TOOL_NAME}|{TASK_TOOL_NAME}|{CODEX_AGENT_TOOL_NAME}"
    )
    registered_command = matching_groups[0]["hooks"][0]["command"]
    assert registered_command.endswith(
        f"/hooks/blocking/{CALLING_HOOK_NAME}"
    )
    assert (_HOOKS_TREE / "blocking" / CALLING_HOOK_NAME).is_file()
def test_registered_command_runs_under_windows_cmd_for_allow_and_deny() -> None:
    hooks_configuration = json.loads(
        (_HOOKS_TREE / "hooks.json").read_text(encoding="utf-8")
    )
    matching_group = next(
        each_group
        for each_group in hooks_configuration["hooks"]["PreToolUse"]
        if CALLING_HOOK_NAME
        in " ".join(each_hook["command"] for each_hook in each_group["hooks"])
    )
    registered_command = matching_group["hooks"][0]["command"]
    assert registered_command.startswith("python ")
    command_line = registered_command.replace(
        "${CLAUDE_PLUGIN_ROOT}",
        str(_HOOKS_TREE.parent).replace("\\", "/"),
    )

    for each_service_tier, expected_output in (
        (FAST_SERVICE_TIER, ""),
        ("flex", _DENY_DECISION),
    ):
        completed_process = subprocess.run(
            command_line,
            input=json.dumps(_spawn_payload(service_tier=each_service_tier)),
            capture_output=True,
            shell=True,
            text=True,
            check=False,
        )
        assert completed_process.returncode == 0, completed_process.stderr
        if expected_output == "":
            assert completed_process.stdout == ""
        else:
            assert (
                json.loads(completed_process.stdout)["hookSpecificOutput"][
                    "permissionDecision"
                ]
                == expected_output
            )
