"""Unit tests for the fable_spawn_gate PreToolUse hook.

Covers the decision table. A spawn at model ``fable`` whose prompt lacks the
authorization marker is denied, and the deny reason names both the marker and
the advisor-protocol document. The same spawn carrying the marker is allowed.
A spawn at any other model tier, and a spawn with no ``model`` field, pass
whether or not the marker is present. One test reads ``hooks.json`` and
asserts the gate is registered on a matcher covering both spawn tool names.
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import sys
from typing import Any
from unittest import mock

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_TREE = _HOOK_DIR.parent
for each_path in (str(_HOOK_DIR), str(_HOOKS_TREE)):
    if each_path not in sys.path:
        sys.path.insert(0, each_path)

hook_spec = importlib.util.spec_from_file_location(
    "fable_spawn_gate",
    _HOOK_DIR / "fable_spawn_gate.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

from hooks_constants.fable_spawn_gate_constants import (
    ADVISOR_PROTOCOL_DOCUMENT_PATH,
    AGENT_TOOL_NAME,
    FABLE_MODEL_ALIAS,
    FABLE_SPAWN_AUTHORIZATION_MARKER,
    TASK_TOOL_NAME,
)

_GATE_SCRIPT_BASENAME = "fable_spawn_gate.py"
_ADVISOR_SUBAGENT_TYPE = "session-advisor"
_OPUS_MODEL_ALIAS = "opus"
_SONNET_MODEL_ALIAS = "sonnet"
_TITLE_CASE_FABLE_MODEL = "Fable"
_FULL_FABLE_MODEL_ID = "claude-fable-5"
_FULL_SONNET_MODEL_ID = "claude-sonnet-4-5"
_ADVISOR_PROTOCOL_PATH = _HOOKS_TREE.parent / "_shared" / "advisor" / "advisor-protocol.md"
_BIND_SECTION_HEADING = "## Warm-up (once per session)"
_MARKDOWN_SECTION_HEADING_PREFIX = "\n## "
_UNMARKED_PROMPT = "Audit the changed lines and report each finding with its path and line."
_ADVISOR_BIND_PROMPT = (
    "You are the standing session advisor for this run. "
    f"{FABLE_SPAWN_AUTHORIZATION_MARKER} "
    "Answer every consult with ENDORSE, CORRECTION, PLAN, or STOP."
)


def _spawn_payload(
    *,
    tool_name: str = AGENT_TOOL_NAME,
    model: str | None = FABLE_MODEL_ALIAS,
    prompt: str = _UNMARKED_PROMPT,
) -> dict[str, Any]:
    """Build a PreToolUse spawn payload for the decision table.

    Args:
        tool_name: The spawning tool name.
        model: The model alias, or None to leave the field out entirely.
        prompt: The spawn prompt text.

    Returns:
        The payload mapping a hook reads from stdin.
    """
    all_tool_input: dict[str, Any] = {
        "subagent_type": _ADVISOR_SUBAGENT_TYPE,
        "description": "Bind the session advisor",
        "prompt": prompt,
    }
    if model is not None:
        all_tool_input["model"] = model
    return {"tool_name": tool_name, "tool_input": all_tool_input}


def _run_main_with_io(input_text: str) -> str:
    """Run the gate's main against stdin text and return its stdout.

    Args:
        input_text: The raw stdin text the gate reads.

    Returns:
        Everything the gate wrote to stdout — empty on an allow.
    """
    with mock.patch("sys.stdin", io.StringIO(input_text)):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as captured_stdout:
            try:
                hook_module.main()
            except SystemExit:
                pass
            return captured_stdout.getvalue()


def _decision_for(payload: dict[str, Any]) -> str:
    """Return the gate's permissionDecision for one spawn payload.

    Args:
        payload: The PreToolUse payload to feed the gate.

    Returns:
        The decision string from the deny payload.
    """
    captured_output = _run_main_with_io(json.dumps(payload))
    return json.loads(captured_output)["hookSpecificOutput"]["permissionDecision"]


def test_should_deny_fable_spawn_without_the_marker() -> None:
    assert _decision_for(_spawn_payload()) == "deny"


def test_should_allow_fable_spawn_carrying_the_marker() -> None:
    payload = _spawn_payload(prompt=_ADVISOR_BIND_PROMPT)
    assert _run_main_with_io(json.dumps(payload)) == ""


def test_should_allow_opus_spawn_without_the_marker() -> None:
    payload = _spawn_payload(model=_OPUS_MODEL_ALIAS)
    assert _run_main_with_io(json.dumps(payload)) == ""


def test_should_allow_sonnet_spawn_carrying_the_marker() -> None:
    payload = _spawn_payload(model=_SONNET_MODEL_ALIAS, prompt=_ADVISOR_BIND_PROMPT)
    assert _run_main_with_io(json.dumps(payload)) == ""


def test_should_allow_spawn_with_no_model_field() -> None:
    payload = _spawn_payload(model=None)
    assert _run_main_with_io(json.dumps(payload)) == ""


def test_should_deny_title_case_fable_spawn_without_the_marker() -> None:
    assert _decision_for(_spawn_payload(model=_TITLE_CASE_FABLE_MODEL)) == "deny"


def test_should_deny_full_model_id_fable_spawn_without_the_marker() -> None:
    assert _decision_for(_spawn_payload(model=_FULL_FABLE_MODEL_ID)) == "deny"


def test_should_allow_full_model_id_fable_spawn_carrying_the_marker() -> None:
    payload = _spawn_payload(model=_FULL_FABLE_MODEL_ID, prompt=_ADVISOR_BIND_PROMPT)
    assert _run_main_with_io(json.dumps(payload)) == ""


def test_should_allow_full_model_id_sonnet_spawn_without_the_marker() -> None:
    payload = _spawn_payload(model=_FULL_SONNET_MODEL_ID)
    assert _run_main_with_io(json.dumps(payload)) == ""


def test_should_deny_fable_task_spawn_without_the_marker() -> None:
    assert _decision_for(_spawn_payload(tool_name=TASK_TOOL_NAME)) == "deny"


def test_should_deny_fable_spawn_whose_prompt_field_is_absent() -> None:
    payload: dict[str, Any] = {
        "tool_name": AGENT_TOOL_NAME,
        "tool_input": {
            "subagent_type": _ADVISOR_SUBAGENT_TYPE,
            "model": FABLE_MODEL_ALIAS,
        },
    }
    assert _decision_for(payload) == "deny"


def test_deny_reason_names_the_marker_and_the_advisor_protocol_document() -> None:
    captured_output = _run_main_with_io(json.dumps(_spawn_payload()))
    deny_reason = json.loads(captured_output)["hookSpecificOutput"][
        "permissionDecisionReason"
    ]
    assert FABLE_SPAWN_AUTHORIZATION_MARKER in deny_reason
    assert ADVISOR_PROTOCOL_DOCUMENT_PATH in deny_reason


def test_should_allow_when_the_payload_is_malformed_json() -> None:
    assert _run_main_with_io("not valid json {{{") == ""


def _matchers_registering_the_gate() -> list[str]:
    """Return every PreToolUse matcher whose group runs this gate.

    Returns:
        The matcher strings of the registration groups naming the gate script.
    """
    manifest_record = json.loads(
        (_HOOKS_TREE / "hooks.json").read_text(encoding="utf-8")
    )
    all_matchers: list[str] = []
    for each_group in manifest_record["hooks"]["PreToolUse"]:
        for each_hook in each_group.get("hooks", []):
            if _GATE_SCRIPT_BASENAME in each_hook.get("command", ""):
                all_matchers.append(each_group.get("matcher", ""))
    return all_matchers


def test_gate_is_registered_on_a_matcher_covering_both_spawn_tools() -> None:
    all_matchers = _matchers_registering_the_gate()
    assert len(all_matchers) == 1
    assert AGENT_TOOL_NAME in all_matchers[0]
    assert TASK_TOOL_NAME in all_matchers[0]


def _bind_section_text() -> str:
    """Return the advisor-protocol warm-up section that documents the bind.

    Returns:
        The section text running from its heading to the next heading.
    """
    document_text = _ADVISOR_PROTOCOL_PATH.read_text(encoding="utf-8")
    section_start = document_text.index(_BIND_SECTION_HEADING)
    section_body = document_text[section_start + len(_BIND_SECTION_HEADING) :]
    next_heading_start = section_body.find(_MARKDOWN_SECTION_HEADING_PREFIX)
    if next_heading_start < 0:
        return section_body
    return section_body[:next_heading_start]


def test_advisor_protocol_bind_section_names_the_marker_token() -> None:
    assert FABLE_SPAWN_AUTHORIZATION_MARKER in _bind_section_text()
