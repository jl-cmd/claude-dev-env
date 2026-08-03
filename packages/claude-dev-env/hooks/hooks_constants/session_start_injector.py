"""Shared SessionStart context injector for starter hooks.

Pure decision helper: normalize the SessionStart ``source``, honor enable and
timeout configuration, and return a structured result every caller can emit as
``additionalContext`` or ignore.

::

    inject({"source": "startup"}, config)  -> status ok + context for startup
    inject({"source": "resume"}, disabled) -> status disabled, no context
    inject({"source": "weird"}, config)    -> status unknown_source
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from hooks_constants.session_start_injector_constants import (
    ALL_DEFAULT_CONTEXT_BY_SOURCE,
    ALL_INJECTOR_ENABLED_ENV_VALUES,
    ALL_KNOWN_SESSION_START_SOURCES,
    DEFAULT_INJECTOR_TIMEOUT_MILLISECONDS,
    INJECTION_STATUS_DISABLED,
    INJECTION_STATUS_OK,
    INJECTION_STATUS_TIMEOUT,
    INJECTION_STATUS_UNKNOWN_SOURCE,
    MILLISECONDS_PER_SECOND,
    SESSION_START_INJECTOR_ENABLED_ENV_VAR,
    SESSION_START_SOURCE_PAYLOAD_KEY,
    SESSION_START_SOURCE_UNKNOWN,
)


@dataclass(frozen=True)
class InjectorConfiguration:
    """Runtime knobs for one SessionStart injection.

    Attributes:
        is_enabled: When False, inject returns quickly with status disabled.
        timeout_milliseconds: Budget; at or below zero yields status timeout.
        context_by_source: Map of known source -> additionalContext text.
        default_context_for_unknown: Context when source is not a known value.
    """

    is_enabled: bool
    timeout_milliseconds: int
    context_by_source: Mapping[str, str]
    default_context_for_unknown: str = ""


@dataclass(frozen=True)
class InjectionResult:
    """Structured outcome of one inject call.

    Attributes:
        source: Normalized SessionStart source (or ``unknown``).
        status: One of the INJECTION_STATUS_* constants.
        additional_context: Text to emit, empty when not injected.
        latency_milliseconds: Wall time for this inject call.
        is_context_injected: True when additional_context is non-empty.
    """

    source: str
    status: str
    additional_context: str
    latency_milliseconds: float
    is_context_injected: bool


def injector_enabled_in_environment() -> bool:
    """Return whether the injector is enabled from the environment.

    Unset or empty means enabled (default on). Explicit falsey values disable.
    """
    raw_setting = os.environ.get(SESSION_START_INJECTOR_ENABLED_ENV_VAR)
    if raw_setting is None or raw_setting.strip() == "":
        return True
    return raw_setting.strip().lower() in ALL_INJECTOR_ENABLED_ENV_VALUES


def default_injector_configuration() -> InjectorConfiguration:
    """Build the default configuration from environment and constants."""
    return InjectorConfiguration(
        is_enabled=injector_enabled_in_environment(),
        timeout_milliseconds=DEFAULT_INJECTOR_TIMEOUT_MILLISECONDS,
        context_by_source=dict(ALL_DEFAULT_CONTEXT_BY_SOURCE),
        default_context_for_unknown="",
    )


def normalize_session_start_source(payload_by_key: Mapping[str, object]) -> str:
    """Return the SessionStart source string, or unknown when missing/invalid."""
    raw_source = payload_by_key.get(SESSION_START_SOURCE_PAYLOAD_KEY, "")
    if not isinstance(raw_source, str):
        return SESSION_START_SOURCE_UNKNOWN
    normalized_source = raw_source.strip().lower()
    if not normalized_source:
        return SESSION_START_SOURCE_UNKNOWN
    if normalized_source not in ALL_KNOWN_SESSION_START_SOURCES:
        return SESSION_START_SOURCE_UNKNOWN
    return normalized_source


def inject_session_start_context(
    payload_by_key: Mapping[str, object],
    configuration: InjectorConfiguration,
    *,
    clock: Callable[[], float] | None = None,
) -> InjectionResult:
    """Decide SessionStart context for one payload under the given configuration.

    Args:
        payload_by_key: Parsed SessionStart stdin payload.
        configuration: Enable flag, timeout budget, and per-source context.
        clock: Optional monotonic clock for latency (tests inject a stub).

    Returns:
        An InjectionResult with status, source, context, and latency.
    """
    read_clock = clock if clock is not None else time.perf_counter
    start_time = read_clock()
    normalized_source = normalize_session_start_source(payload_by_key)

    if not configuration.is_enabled:
        status = INJECTION_STATUS_DISABLED
        context_text = ""
    elif configuration.timeout_milliseconds <= 0:
        status = INJECTION_STATUS_TIMEOUT
        context_text = ""
    elif normalized_source == SESSION_START_SOURCE_UNKNOWN:
        status = INJECTION_STATUS_UNKNOWN_SOURCE
        context_text = configuration.default_context_for_unknown
    else:
        status = INJECTION_STATUS_OK
        context_text = configuration.context_by_source.get(normalized_source, "")

    end_time = read_clock()
    return InjectionResult(
        source=normalized_source,
        status=status,
        additional_context=context_text,
        latency_milliseconds=(end_time - start_time)
        * MILLISECONDS_PER_SECOND,
        is_context_injected=bool(context_text),
    )


def build_additional_context_payload(injection_result: InjectionResult) -> dict[str, str]:
    """Return the SessionStart stdout object when context was injected.

    Args:
        injection_result: Result from inject_session_start_context.

    Returns:
        ``{"additionalContext": ...}`` when injected, else empty dict.
    """
    if not injection_result.is_context_injected:
        return {}
    return {"additionalContext": injection_result.additional_context}

