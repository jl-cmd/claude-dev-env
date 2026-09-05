"""Support functions for the Codex Astra advisor."""

from __future__ import annotations

import importlib
import json
import math
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from advisor_scripts_constants.astra_advisor_constants import (
    ASTRA_FALLBACK_KIND_BROKEN,
    ASTRA_FALLBACK_KIND_DECLINED,
    ASTRA_INVALID_SIGNAL_REASON,
    ASTRA_MALFORMED_JSONL_REASON,
    ASTRA_MISSING_SESSION_REASON,
    ASTRA_PREFLIGHT_FAILURE_REASON,
    ASTRA_PROBE_TIMEOUT_REASON,
    ASTRA_REPLY_FAILURE_REASON,
    ASTRA_USAGE_PROBE_TIMEOUT_SECONDS,
    CLAUDE_CONFIG_DIRECTORY_NAME,
    USAGE_PROBE_FILENAME,
    USAGE_PROBE_PACKAGE_DIRECTORY_NAME,
    USAGE_PROBE_SCRIPTS_DIRECTORY_NAME,
    USAGE_PROBE_SHARED_DIRECTORY_NAME,
)
from advisor_scripts_constants.advisor_route_constants import (
    ADVISOR_FALLBACK_RESULT,
    ADVISOR_FALLBACK_TIER,
    ADVISOR_MODEL_TIER,
    CODEX_BIND_SUCCESS_TOKEN,
    ALL_ADVISOR_GUIDANCE_SIGNALS,
)


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


def _preflight_fallback(
    reason: str, percent_left: float | None, fallback_kind: str
) -> AstraPreflight:
    return AstraPreflight(False, percent_left, reason, fallback_kind)


def reply_fallback(
    reason: str,
    is_astra_enabled: bool,
    fallback_kind: str | None = ASTRA_FALLBACK_KIND_BROKEN,
) -> CodexAstraAdvisorReply:
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


def _reply_success(
    session_id: str, guidance: str, signal: str
) -> CodexAstraAdvisorReply:
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


def resolve_usage_probe_path(home_directory: Path) -> Path:
    """Return the installed Codex usage-probe path."""
    return (
        home_directory
        / CLAUDE_CONFIG_DIRECTORY_NAME
        / USAGE_PROBE_SHARED_DIRECTORY_NAME
        / USAGE_PROBE_PACKAGE_DIRECTORY_NAME
        / USAGE_PROBE_SCRIPTS_DIRECTORY_NAME
        / USAGE_PROBE_FILENAME
    )


def _load_usage_gate(probe_path: Path) -> Callable[[float], bool]:
    probe_directory = str(probe_path.parent)
    if probe_directory not in sys.path:
        sys.path.insert(0, probe_directory)
    return importlib.import_module("codex_usage_probe").is_codex_review_required


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


def _run_probe(
    probe_path: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> subprocess.CompletedProcess[str]:
    return process_runner(
        [sys.executable, str(probe_path)],
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=ASTRA_USAGE_PROBE_TIMEOUT_SECONDS,
    )


def _preflight_from_probe(
    probe_path: Path, completed: subprocess.CompletedProcess[str]
) -> AstraPreflight:
    if completed.returncode != 0:
        reason = f"{ASTRA_PREFLIGHT_FAILURE_REASON}: probe exit {completed.returncode}"
        return _preflight_fallback(reason, None, ASTRA_FALLBACK_KIND_BROKEN)
    percent_left, parse_reason = _parse_probe_percent(completed.stdout)
    if parse_reason is not None or percent_left is None:
        reason = f"{ASTRA_PREFLIGHT_FAILURE_REASON}: {parse_reason or 'usage meter is unknown'}"
        return _preflight_fallback(reason, None, ASTRA_FALLBACK_KIND_BROKEN)
    if not _load_usage_gate(probe_path)(percent_left):
        reason = f"{ASTRA_PREFLIGHT_FAILURE_REASON}: usage meter is at or below the gate"
        return _preflight_fallback(reason, percent_left, ASTRA_FALLBACK_KIND_DECLINED)
    return AstraPreflight(True, percent_left, "usage meter is above the Astra gate")


def run_astra_preflight(
    probe_path: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> AstraPreflight:
    """Run the usage probe and evaluate Astra eligibility."""
    try:
        completed = _run_probe(probe_path, process_runner)
        return _preflight_from_probe(probe_path, completed)
    except subprocess.TimeoutExpired as error:
        return _preflight_fallback(
            f"{ASTRA_PROBE_TIMEOUT_REASON}: {error}", None, ASTRA_FALLBACK_KIND_BROKEN
        )
    except (OSError, subprocess.SubprocessError, ImportError, AttributeError, TypeError, ValueError) as error:
        return _preflight_fallback(
            f"{ASTRA_PREFLIGHT_FAILURE_REASON}: {error}",
            None,
            ASTRA_FALLBACK_KIND_BROKEN,
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


def parse_codex_jsonl_reply(
    jsonl_text: str,
    existing_session_id: str | None,
    is_astra_enabled: bool,
    fallback_kind: str | None = ASTRA_FALLBACK_KIND_BROKEN,
) -> CodexAstraAdvisorReply:
    """Parse Codex JSONL into a typed Astra advisor reply."""
    session_id: str | None = None
    guidance: str | None = None
    try:
        for each_line in jsonl_text.splitlines():
            if not each_line.strip():
                continue
            discovered_session_id, discovered_guidance = _parse_event_line(each_line)
            session_id = discovered_session_id or session_id
            guidance = discovered_guidance or guidance
    except (TypeError, json.JSONDecodeError):
        return reply_fallback(ASTRA_MALFORMED_JSONL_REASON, is_astra_enabled, fallback_kind)
    if session_id is None or (existing_session_id is not None and session_id != existing_session_id):
        return reply_fallback(ASTRA_MISSING_SESSION_REASON, is_astra_enabled, fallback_kind)
    if not guidance:
        return reply_fallback(ASTRA_REPLY_FAILURE_REASON, is_astra_enabled, fallback_kind)
    signal = _guidance_signal(guidance)
    if signal is None:
        return reply_fallback(ASTRA_INVALID_SIGNAL_REASON, is_astra_enabled, fallback_kind)
    return _reply_success(session_id, guidance, signal)
