"""Constants for the Codex Luna fast-mode spawn gate.

The gate checks the model and service tier fields on Agent, Task, and native
Codex multi-agent spawn calls. Agent and Task require exact ``fast``. Native
Codex accepts exact ``fast`` or ``priority`` for Luna models.
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
PRIORITY_SERVICE_TIER: str = "priority"
MODEL_SEGMENT_SPLIT_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9]+")

TOOL_NAME_FIELD_NAME: str = "tool_name"
TOOL_INPUT_FIELD_NAME: str = "tool_input"
MODEL_FIELD_NAME: str = "model"
SERVICE_TIER_FIELD_NAME: str = "service_tier"

CALLING_HOOK_NAME: str = "luna_fast_mode_gate.py"
HOOK_EVENT_NAME: str = "PreToolUse"

DENY_REASON: str = (
    "BLOCKED [luna-fast-mode-gate]: Agent and Task Luna spawns require "
    "service_tier fast. Native Codex Luna spawns require service_tier fast "
    "or priority. Retry with an allowed service_tier."
)

DENY_ADDITIONAL_CONTEXT: str = (
    "[luna-fast-mode-gate] Agent and Task Luna spawns require service_tier "
    "fast. Native Codex Luna spawns accept service_tier fast or priority. "
    "Retry with an allowed service_tier."
)

DENY_PREVIEW_TEMPLATE: str = "model={model_text} service_tier={service_tier_text}"
MAXIMUM_PREVIEW_FIELD_LENGTH: int = 40
