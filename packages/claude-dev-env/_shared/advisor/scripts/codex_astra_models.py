"""Typed values exchanged by the Codex Astra advisor."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class AstraPreflight:
    eligible: bool
    percent_left: float | None
    reason: str
    fallback_kind: str | None = None


@dataclass(frozen=True)
class CodexAstraAdvisorReply:
    session_id: str | None
    guidance: str | None
    successful: bool
    reason: str | None
    is_fallback: bool
    signal: str | None
    astra_enabled: bool
    selected_tier: str
    outcome: str
    fallback_kind: str | None


def _parse_codex_event(each_line: str) -> tuple[str | None, str | None]:
    event = json.loads(each_line)
    if not isinstance(event, dict):
        raise TypeError("event must be an object")
    discovered_session_id: str | None = None
    discovered_guidance: str | None = None
    if event.get("type") == "thread.started":
        raw_session = event.get("thread_id")
        if isinstance(raw_session, str) and raw_session.strip():
            discovered_session_id = raw_session.strip()
    completed_event = event.get("item")
    if event.get("type") == "item.completed" and isinstance(completed_event, dict):
        message_text = completed_event.get("text")
        if completed_event.get("type") == "agent_message" and isinstance(message_text, str):
            discovered_guidance = message_text.strip()
    return discovered_session_id, discovered_guidance


def _parse_probe_percent(stdout_text: str) -> tuple[float | None, str | None]:
    try:
        report = json.loads(stdout_text)
    except (TypeError, json.JSONDecodeError):
        return None, "usage report is malformed"
    if not isinstance(report, dict):
        return None, "usage report is malformed"
    raw_percent = report.get("percent_left")
    if isinstance(raw_percent, bool) or not isinstance(raw_percent, (int, float)):
        return None, "usage meter is unknown" if raw_percent is None else "usage meter is malformed"
    percent_left = float(raw_percent)
    if not math.isfinite(percent_left):
        return None, "usage meter is malformed"
    return percent_left, None
