"""Tests for the shared SessionStart context injector."""

from __future__ import annotations


import pytest

from hooks_constants.session_start_injector import (
    InjectionResult,
    InjectorConfiguration,
    build_additional_context_payload,
    default_injector_configuration,
    inject_session_start_context,
    injector_enabled_in_environment,
    normalize_session_start_source,
)
from hooks_constants.session_start_injector_constants import (
    INJECTION_STATUS_DISABLED,
    INJECTION_STATUS_OK,
    INJECTION_STATUS_TIMEOUT,
    INJECTION_STATUS_UNKNOWN_SOURCE,
    SESSION_START_INJECTOR_ENABLED_ENV_VAR,
    SESSION_START_SOURCE_CLEAR,
    SESSION_START_SOURCE_COMPACT,
    SESSION_START_SOURCE_RESUME,
    SESSION_START_SOURCE_STARTUP,
    SESSION_START_SOURCE_UNKNOWN,
)


def _configuration(
    *,
    is_enabled: bool = True,
    timeout_milliseconds: int = 50,
    context_by_source: dict[str, str] | None = None,
    default_context_for_unknown: str = "",
) -> InjectorConfiguration:
    return InjectorConfiguration(
        is_enabled=is_enabled,
        timeout_milliseconds=timeout_milliseconds,
        context_by_source=context_by_source
        or {
            SESSION_START_SOURCE_STARTUP: "startup-context",
            SESSION_START_SOURCE_RESUME: "resume-context",
            SESSION_START_SOURCE_CLEAR: "clear-context",
            SESSION_START_SOURCE_COMPACT: "compact-context",
        },
        default_context_for_unknown=default_context_for_unknown,
    )


def _fixed_clock(all_readings: list[float]) -> object:
    index = {"value": 0}

    def _read() -> float:
        reading = all_readings[min(index["value"], len(all_readings) - 1)]
        index["value"] += 1
        return reading

    return _read


@pytest.mark.parametrize(
    ("source", "expected_context"),
    [
        (SESSION_START_SOURCE_STARTUP, "startup-context"),
        (SESSION_START_SOURCE_RESUME, "resume-context"),
        (SESSION_START_SOURCE_CLEAR, "clear-context"),
        (SESSION_START_SOURCE_COMPACT, "compact-context"),
    ],
)
def test_inject_known_source_returns_ok_with_context(
    source: str, expected_context: str
) -> None:
    result = inject_session_start_context(
        {"source": source},
        _configuration(),
        clock=_fixed_clock([1.0, 1.002]),
    )
    assert result.status == INJECTION_STATUS_OK
    assert result.source == source
    assert result.additional_context == expected_context
    assert result.is_context_injected is True
    assert result.latency_milliseconds == pytest.approx(2.0)


def test_inject_disabled_returns_quickly_without_context() -> None:
    result = inject_session_start_context(
        {"source": SESSION_START_SOURCE_STARTUP},
        _configuration(is_enabled=False),
        clock=_fixed_clock([0.0, 0.0001]),
    )
    assert result.status == INJECTION_STATUS_DISABLED
    assert result.additional_context == ""
    assert result.is_context_injected is False
    assert result.latency_milliseconds < 1.0


def test_inject_timeout_budget_zero_returns_timeout() -> None:
    result = inject_session_start_context(
        {"source": SESSION_START_SOURCE_RESUME},
        _configuration(timeout_milliseconds=0),
        clock=_fixed_clock([0.0, 0.0]),
    )
    assert result.status == INJECTION_STATUS_TIMEOUT
    assert result.is_context_injected is False


def test_inject_unknown_source_is_explicit() -> None:
    result = inject_session_start_context(
        {"source": "not-a-real-source"},
        _configuration(default_context_for_unknown="fallback"),
        clock=_fixed_clock([0.0, 0.001]),
    )
    assert result.status == INJECTION_STATUS_UNKNOWN_SOURCE
    assert result.source == SESSION_START_SOURCE_UNKNOWN
    assert result.additional_context == "fallback"
    assert result.is_context_injected is True


def test_normalize_session_start_source_handles_missing_and_case() -> None:
    assert normalize_session_start_source({}) == SESSION_START_SOURCE_UNKNOWN
    assert (
        normalize_session_start_source({"source": " STARTUP "})
        == SESSION_START_SOURCE_STARTUP
    )
    assert normalize_session_start_source({"source": 12}) == SESSION_START_SOURCE_UNKNOWN


def test_build_additional_context_payload_only_when_injected() -> None:
    injected = InjectionResult(
        source=SESSION_START_SOURCE_STARTUP,
        status=INJECTION_STATUS_OK,
        additional_context="hello",
        latency_milliseconds=1.0,
        is_context_injected=True,
    )
    empty = InjectionResult(
        source=SESSION_START_SOURCE_STARTUP,
        status=INJECTION_STATUS_DISABLED,
        additional_context="",
        latency_milliseconds=0.1,
        is_context_injected=False,
    )
    assert build_additional_context_payload(injected) == {
        "additionalContext": "hello"
    }
    assert build_additional_context_payload(empty) == {}


def test_injector_enabled_in_environment_default_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(SESSION_START_INJECTOR_ENABLED_ENV_VAR, raising=False)
    assert injector_enabled_in_environment() is True
    monkeypatch.setenv(SESSION_START_INJECTOR_ENABLED_ENV_VAR, "0")
    assert injector_enabled_in_environment() is False
    monkeypatch.setenv(SESSION_START_INJECTOR_ENABLED_ENV_VAR, "true")
    assert injector_enabled_in_environment() is True


def test_default_injector_configuration_reads_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SESSION_START_INJECTOR_ENABLED_ENV_VAR, "off")
    configuration = default_injector_configuration()
    assert configuration.is_enabled is False

