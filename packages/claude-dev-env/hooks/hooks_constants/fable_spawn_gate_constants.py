"""Constants for the fable-tier subagent spawn gate.

The gate denies an ``Agent`` or ``Task`` spawn at the fable tier whose
``prompt`` lacks ``FABLE_SPAWN_AUTHORIZATION_MARKER``. ``DENY_REASON`` points
at the protocol document rather than quoting the token, so pasting a denial
into a retry prompt authorizes nothing.
``MODEL_SEGMENT_SPLIT_PATTERN`` finds that tier in a full model id too::

    fable           -> ['fable']                  flag: fable tier
    claude-fable-5  -> ['claude', 'fable', '5']   flag: fable tier
    claude-sonnet-4 -> ['claude', 'sonnet', '4']  ok:   another tier

Every literal the gate body reads lives here. ``AGENT_TOOL_NAME`` and
``TASK_TOOL_NAME`` name the spawn tools the gate evaluates.
"""

from __future__ import annotations

import re

AGENT_TOOL_NAME: str = "Agent"
TASK_TOOL_NAME: str = "Task"

ALL_SPAWN_TOOL_NAMES: frozenset[str] = frozenset({AGENT_TOOL_NAME, TASK_TOOL_NAME})

FABLE_MODEL_ALIAS: str = "fable"
MODEL_SEGMENT_SPLIT_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9]+")
FABLE_SPAWN_AUTHORIZATION_MARKER: str = "FABLE-SPAWN-AUTHORIZED"
ADVISOR_PROTOCOL_DOCUMENT_PATH: str = "_shared/advisor/advisor-protocol.md"

TOOL_NAME_FIELD_NAME: str = "tool_name"
TOOL_INPUT_FIELD_NAME: str = "tool_input"
MODEL_FIELD_NAME: str = "model"
PROMPT_FIELD_NAME: str = "prompt"

CALLING_HOOK_NAME: str = "fable_spawn_gate.py"
HOOK_EVENT_NAME: str = "PreToolUse"

DENY_REASON: str = (
    "BLOCKED [fable-spawn-gate]: Fable-tier spawns require the authorization "
    f"token named in {ADVISOR_PROTOCOL_DOCUMENT_PATH}. Place that token as "
    "plain text in the spawn prompt, or set model to opus, sonnet, or haiku. "
    "The gate checks the model tier and marker presence."
)

DENY_ADDITIONAL_CONTEXT: str = (
    "[fable-spawn-gate] Use model opus or an opus-equivalent tier such as sonnet "
    "or haiku for this spawn. "
    "For an authorized fable bind, place the token named in "
    f"{ADVISOR_PROTOCOL_DOCUMENT_PATH} as plain text in the spawn prompt, "
    "then retry. The gate checks the model tier and marker presence."
)

DENY_PREVIEW_TEMPLATE: str = "model={model_text} marker_present=False"
MAXIMUM_PREVIEW_MODEL_LENGTH: int = 40
