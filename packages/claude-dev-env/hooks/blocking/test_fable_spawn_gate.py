"""Unit tests for the fable_spawn_gate PreToolUse hook.

Covers the decision table. A spawn at model ``fable`` whose prompt lacks the
authorization marker is denied, and the deny reason points at the
advisor-protocol document while carrying no copy of the token — one row holds
the reason token-free, and its anti-corollary feeds that reason back as a
retry prompt and expects a second denial. The same spawn carrying the marker
is allowed. A spawn at any other model tier, and a spawn with no ``model``
field, pass whether or not the marker is present. One test reads
``hooks.json`` and asserts the gate is registered on a matcher covering both
spawn tool names.

Token pins read the warm-up section and each consuming skill. Two doc-gate
agreement tests assemble a spawn prompt out of the advisor-protocol wording a
warm-up bind and a drift re-spawn follow, and run each through the gate, so
wording that stops naming the marker fails here. Two deny-path tests read the
preview the gate hands the block logger and hold it bounded and scoped to the
model field.
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
    CALLING_HOOK_NAME,
    FABLE_MODEL_ALIAS,
    FABLE_SPAWN_AUTHORIZATION_MARKER,
    TASK_TOOL_NAME,
)

_ADVISOR_SUBAGENT_TYPE = "session-advisor"
_OPUS_MODEL_ALIAS = "opus"
_SONNET_MODEL_ALIAS = "sonnet"
_TITLE_CASE_FABLE_MODEL = "Fable"
_FULL_FABLE_MODEL_ID = "claude-fable-5"
_FULL_SONNET_MODEL_ID = "claude-sonnet-4-5"
_PACKAGE_ROOT = _HOOKS_TREE.parent
_ADVISOR_PROTOCOL_PATH = _PACKAGE_ROOT / "_shared" / "advisor" / "advisor-protocol.md"
_ADVISOR_PROTOCOL_TEXT = _ADVISOR_PROTOCOL_PATH.read_text(encoding="utf-8")
_ALL_CONSUMING_SKILL_NAMES = ("team-advisor", "orchestrator", "orchestrator-refresh")
_ALL_CONSUMING_SKILL_PATHS = tuple(
    _PACKAGE_ROOT / "skills" / each_skill_name / "SKILL.md"
    for each_skill_name in _ALL_CONSUMING_SKILL_NAMES
)
_skill_pin_ids = _ALL_CONSUMING_SKILL_NAMES
_BIND_SECTION_HEADING = "## Warm-up (once per session)"
_MARKDOWN_SECTION_HEADING_PREFIX = "\n## "
_RESPAWN_PARAGRAPH_MARKER = "**Re-spawn on drift.**"
_WARM_UP_PROMPT_BULLET_MARKER = "- `prompt`: the charter below."
_PARAGRAPH_SEPARATOR = "\n\n"
_MULTI_KILOBYTE_PROMPT = "Audit the changed lines and report each finding. " * 200
_MAXIMUM_DENY_PREVIEW_LENGTH = 120
_MARKER_STATE_FIELD_NAME = "marker_present"
_PROMPT_BODY_SAMPLE = "Audit the changed lines"
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


def _deny_reason_for(payload: dict[str, Any]) -> str:
    """Return the permissionDecisionReason the gate writes for one payload.

    Args:
        payload: The PreToolUse payload the gate denies.

    Returns:
        The deny reason text.
    """
    captured_output = _run_main_with_io(json.dumps(payload))
    return str(
        json.loads(captured_output)["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_deny_reason_names_the_document_without_the_token() -> None:
    deny_reason = _deny_reason_for(_spawn_payload())
    assert ADVISOR_PROTOCOL_DOCUMENT_PATH in deny_reason
    assert FABLE_SPAWN_AUTHORIZATION_MARKER not in deny_reason


def test_spawn_prompt_carrying_the_deny_text_still_denies() -> None:
    deny_reason = _deny_reason_for(_spawn_payload())
    assert _decision_for(_spawn_payload(prompt=deny_reason)) == "deny"


def test_should_allow_when_the_payload_is_malformed_json() -> None:
    assert _run_main_with_io("not valid json {{{") == ""


def _denial_preview_for(payload: dict[str, Any]) -> str:
    """Return the offending-input preview the gate hands the block logger.

    Args:
        payload: The PreToolUse payload the gate denies.

    Returns:
        The ``offending_input_preview`` argument of the logged block.
    """
    with mock.patch.object(hook_module, "log_hook_block") as recorded_block:
        _run_main_with_io(json.dumps(payload))
    return str(recorded_block.call_args.kwargs["offending_input_preview"])


def test_deny_preview_stays_bounded_on_a_multi_kilobyte_prompt() -> None:
    preview = _denial_preview_for(_spawn_payload(prompt=_MULTI_KILOBYTE_PROMPT))
    assert len(preview) <= _MAXIMUM_DENY_PREVIEW_LENGTH


def test_deny_preview_carries_the_model_and_marker_state_without_the_prompt() -> None:
    preview = _denial_preview_for(_spawn_payload(prompt=_MULTI_KILOBYTE_PROMPT))
    assert FABLE_MODEL_ALIAS in preview
    assert _MARKER_STATE_FIELD_NAME in preview
    assert _PROMPT_BODY_SAMPLE not in preview


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
            if CALLING_HOOK_NAME in each_hook.get("command", ""):
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
    section_start = _ADVISOR_PROTOCOL_TEXT.index(_BIND_SECTION_HEADING)
    section_body = _ADVISOR_PROTOCOL_TEXT[section_start + len(_BIND_SECTION_HEADING) :]
    next_heading_start = section_body.find(_MARKDOWN_SECTION_HEADING_PREFIX)
    if next_heading_start < 0:
        return section_body
    return section_body[:next_heading_start]


def test_advisor_protocol_bind_section_names_the_marker_token() -> None:
    assert FABLE_SPAWN_AUTHORIZATION_MARKER in _bind_section_text()


@pytest.mark.parametrize("skill_path", _ALL_CONSUMING_SKILL_PATHS, ids=_skill_pin_ids)
def test_consuming_skill_names_the_marker_token(skill_path: pathlib.Path) -> None:
    assert FABLE_SPAWN_AUTHORIZATION_MARKER in skill_path.read_text(encoding="utf-8")


def _paragraph_starting_at(paragraph_marker: str) -> str:
    """Return the advisor-protocol paragraph that opens with a marker.

    Args:
        paragraph_marker: The literal text opening the paragraph.

    Returns:
        The paragraph text, running from that marker to the blank line that
        closes it.
    """
    paragraph_body = _ADVISOR_PROTOCOL_TEXT[
        _ADVISOR_PROTOCOL_TEXT.index(paragraph_marker) :
    ]
    paragraph_end = paragraph_body.find(_PARAGRAPH_SEPARATOR)
    if paragraph_end < 0:
        return paragraph_body
    return paragraph_body[:paragraph_end]


def _respawn_spawn_prompt() -> str:
    """Assemble the spawn prompt a drift re-spawn writes from the protocol.

    The prompt comes from the re-spawn paragraph alone, so the gate reads
    what that one paragraph tells a session to send.

    Returns:
        The spawn prompt text a session following that paragraph sends.
    """
    return _paragraph_starting_at(_RESPAWN_PARAGRAPH_MARKER)


def test_respawn_paragraph_prompt_passes_the_gate_at_the_fable_tier() -> None:
    payload = _spawn_payload(prompt=_respawn_spawn_prompt())
    assert _run_main_with_io(json.dumps(payload)) == ""


def _warm_up_spawn_prompt() -> str:
    """Assemble the spawn prompt a warm-up bind writes from the protocol.

    The prompt comes from the spawn-field prompt bullet alone, so the gate
    reads what that one bullet tells a session to send.

    Returns:
        The spawn prompt text a session following that bullet sends.
    """
    return _paragraph_starting_at(_WARM_UP_PROMPT_BULLET_MARKER)


def test_warm_up_prompt_bullet_passes_the_gate_at_the_fable_tier() -> None:
    payload = _spawn_payload(prompt=_warm_up_spawn_prompt())
    assert _run_main_with_io(json.dumps(payload)) == ""
