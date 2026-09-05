"""Parse and construct typed Astra advisor replies."""

from __future__ import annotations

import json
from dataclasses import dataclass

from advisor_scripts_constants.advisor_route_constants import (
    ADVISOR_FALLBACK_RESULT,
    ADVISOR_FALLBACK_TIER,
    ADVISOR_MODEL_TIER,
    ALL_ADVISOR_GUIDANCE_SIGNALS,
    CODEX_BIND_SUCCESS_TOKEN,
)
from advisor_scripts_constants.astra_advisor_constants import (
    ASTRA_FALLBACK_KIND_BROKEN,
    ASTRA_INVALID_SIGNAL_REASON,
    ASTRA_MALFORMED_JSONL_REASON,
    ASTRA_MISSING_SESSION_REASON,
    ASTRA_REPLY_FAILURE_REASON,
)


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


def build_fallback_reply(
    reason: str,
    is_astra_enabled: bool,
    fallback_kind: str | None = ASTRA_FALLBACK_KIND_BROKEN,
) -> CodexAstraAdvisorReply:
    """Build a typed fallback reply.

    Args:
        reason: Explanation for the fallback.
        is_astra_enabled: Whether the Astra route was enabled.
        fallback_kind: Classification of the fallback.

    Returns:
        A typed fallback reply.
    """
    return CodexAstraAdvisorReply(
        None,
        None,
        False,
        reason,
        True,
        None,
        is_astra_enabled,
        ADVISOR_FALLBACK_TIER,
        ADVISOR_FALLBACK_RESULT,
        fallback_kind,
    )


def build_success_reply(
    session_id: str, guidance: str, signal: str
) -> CodexAstraAdvisorReply:
    """Build a successful typed reply.

    Args:
        session_id: Codex session identifier.
        guidance: Advisor guidance text.
        signal: Leading guidance signal.

    Returns:
        A successful typed reply.
    """
    return CodexAstraAdvisorReply(
        session_id,
        guidance,
        True,
        None,
        False,
        signal,
        True,
        ADVISOR_MODEL_TIER,
        CODEX_BIND_SUCCESS_TOKEN,
        None,
    )


def _guidance_signal(guidance: str) -> str | None:
    for each_line in guidance.splitlines():
        candidate = each_line.strip()
        if candidate:
            return candidate if candidate in ALL_ADVISOR_GUIDANCE_SIGNALS else None
    return None


def _parse_event_line(each_line: str) -> tuple[str | None, str | None]:
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


def _collect_reply_parts(jsonl_text: str) -> tuple[str | None, str | None]:
    session_id: str | None = None
    guidance: str | None = None
    for each_line in jsonl_text.splitlines():
        if each_line.strip():
            discovered_session_id, discovered_guidance = _parse_event_line(each_line)
            session_id = discovered_session_id or session_id
            guidance = discovered_guidance or guidance
    return session_id, guidance


def parse_codex_jsonl_reply(
    jsonl_text: str,
    existing_session_id: str | None,
    is_astra_enabled: bool,
    fallback_kind: str | None = None,
) -> CodexAstraAdvisorReply:
    """Parse Codex JSONL into a typed Astra advisor reply.

    Args:
        jsonl_text: JSONL emitted by Codex.
        existing_session_id: Existing session expected on resume.
        is_astra_enabled: Whether this route had Astra enabled.

    Returns:
        A successful advisor reply or typed fallback.
    """
    try:
        session_id, guidance = _collect_reply_parts(jsonl_text)
    except (TypeError, json.JSONDecodeError):
        return build_fallback_reply(ASTRA_MALFORMED_JSONL_REASON, is_astra_enabled, fallback_kind)
    if session_id is None or (existing_session_id is not None and session_id != existing_session_id):
        return build_fallback_reply(ASTRA_MISSING_SESSION_REASON, is_astra_enabled, fallback_kind)
    if not guidance:
        return build_fallback_reply(ASTRA_REPLY_FAILURE_REASON, is_astra_enabled, fallback_kind)
    signal = _guidance_signal(guidance)
    if signal is None:
        return build_fallback_reply(ASTRA_INVALID_SIGNAL_REASON, is_astra_enabled, fallback_kind)
    return build_success_reply(session_id, guidance, signal)
