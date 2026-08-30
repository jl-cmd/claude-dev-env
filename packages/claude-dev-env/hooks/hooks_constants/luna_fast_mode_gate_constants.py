"""Constants for the Codex Luna fast-mode spawn gate.

The gate checks the model and service tier fields on Agent, Task, and native
Codex multi-agent spawn calls. Only the exact ``fast`` service tier passes for
a model whose delimiter-separated identifier contains the ``luna`` segment.
"""

from __future__ import annotations

import re

AGENT_TOOL_NAME: str = "Agent"
TASK_TOOL_NAME: str = "Task"
CODEX_AGENT_TOOL_NAME: str = "multi_agent_v1__spawn_agent"
ALL_SPAWN_TOOL_NAMES: frozenset[str] = frozenset(
    {AGENT_TOOL_NAME, TASK_TOOL_NAME, CODEX_AGENT_TOOL_NAME}
)

LUNA_MODEL_ALIAS: str = "luna"
FAST_SERVICE_TIER: str = "fast"
MODEL_SEGMENT_SPLIT_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9]+")

TOOL_NAME_FIELD_NAME: str = "tool_name"
TOOL_INPUT_FIELD_NAME: str = "tool_input"
MODEL_FIELD_NAME: str = "model"
SERVICE_TIER_FIELD_NAME: str = "service_tier"

CALLING_HOOK_NAME: str = "luna_fast_mode_gate.py"
HOOK_EVENT_NAME: str = "PreToolUse"

DENY_REASON: str = (
    "BLOCKED [luna-fast-mode-gate]: this Luna spawn does not set its "
    "service_tier field to fast. Set service_tier to fast and retry."
)

DENY_ADDITIONAL_CONTEXT: str = (
    "[luna-fast-mode-gate] This Luna spawn was denied because its service_tier "
    "field is not fast. Set service_tier to fast, then retry."
)

DENY_PREVIEW_TEMPLATE: str = "model={model_text} service_tier={service_tier_text}"
MAXIMUM_PREVIEW_FIELD_LENGTH: int = 40
