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
    "BLOCKED [fable-spawn-gate]: this subagent spawn names the fable tier in "
    "its model field and carries no authorization marker. To authorize a "
    f"fable bind, put the token named in {ADVISOR_PROTOCOL_DOCUMENT_PATH} as "
    "plain text in the spawn prompt (substring match). Otherwise set model "
    "to opus, sonnet, or haiku. The gate checks only model tier and marker "
    "presence — it does not verify which session placed the token."
)

DENY_ADDITIONAL_CONTEXT: str = (
    "[fable-spawn-gate] This Agent/Task spawn was denied: the model field "
    "names the fable tier and the spawn prompt carries no authorization "
    "marker. Preferred recovery: re-spawn at model opus, or an "
    "opus-equivalent tier (sonnet/haiku when opus is unavailable) — those "
    "tiers need no marker. Authorized fable bind only: put the token named "
    f"in {ADVISOR_PROTOCOL_DOCUMENT_PATH} as plain text in the spawn prompt "
    "(substring match), then retry. The gate checks only model tier and "
    "marker presence. Do not paste this denial into a retry prompt — it "
    "does not authorize the spawn."
)

DENY_PREVIEW_TEMPLATE: str = "model={model_text} marker_present=False"
MAXIMUM_PREVIEW_MODEL_LENGTH: int = 40
